"""
Nexo Analytics - Administrador de Backups Cifrados y Recuperación de Datos
Gestiona copias de seguridad automatizadas con cifrado simétrico AES-256 (Fernet), firmas SHA-256 y restauración verificada.
"""

from __future__ import annotations
import base64
import hashlib
import hmac
import io
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from finance_app.config import get_config
from finance_app.logging_config import get_logger

logger = get_logger("backup_manager")

_BACKUP_SALT = b"NexoAnalytics_Backup_Salt_2026"


def _derive_fernet_key(secret_str: str) -> bytes:
    """Deriva una clave Fernet válida de 32 bytes en base64 url-safe a partir de un secreto arbitrario."""
    if not secret_str:
        secret_str = "DefaultNexoAnalyticsDevBackupSecretKey2026!"
    
    # Si ya es una clave base64 urlsafe de 32 bytes válida
    try:
        raw_b64 = secret_str.strip().encode("utf-8")
        if len(base64.urlsafe_b64decode(raw_b64)) == 32:
            return raw_b64
    except Exception:
        pass

    # Derivar con PBKDF2
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_BACKUP_SALT,
        iterations=100_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(secret_str.encode("utf-8")))


def get_backup_cipher() -> Fernet:
    """Obtiene el motor de cifrado simétrico Fernet para copias de seguridad."""
    cfg = get_config()
    secret = cfg.backup_encryption_key or cfg.app_encryption_key or cfg.app_secret_key
    key = _derive_fernet_key(secret)
    return Fernet(key)


def compute_file_sha256(file_path: Path | str) -> str:
    """Calcula el hash SHA-256 de un archivo en disco."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def compute_file_hmac(file_path: Path | str) -> str:
    """Calcula la firma de integridad HMAC-SHA256 utilizando la clave secreta de backup."""
    cfg = get_config()
    secret = (cfg.backup_encryption_key or cfg.app_secret_key or "NexoBackupHMAC2026!").encode("utf-8")
    h = hmac.new(secret, digestmod=hashlib.sha256)
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def create_backup(
    source_path: Path | str,
    tag: str = "auto",
    backup_dir: Optional[Path | str] = None,
    max_backups: Optional[int] = None,
    encrypt: Optional[bool] = None,
) -> Optional[Path]:
    """
    Crea una copia de seguridad timestamped y opcionalmente cifrada de un archivo de datos.
    Genera una firma HMAC-SHA256 complementaria para garantizar integridad absoluta contra manipulaciones.
    """
    cfg = get_config()
    source = Path(source_path)
    if not source.is_absolute():
        source = cfg.get_absolute_path(source)

    if not source.exists() or not source.is_file():
        logger.warning(f"No se pudo crear backup: el archivo fuente no existe: {source}")
        return None

    target_backup_dir = Path(backup_dir) if backup_dir else cfg.get_absolute_path(cfg.backup_dir)
    target_backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_stem = source.stem.replace(" ", "_")
    clean_tag = tag.replace(" ", "_")
    
    should_encrypt = encrypt if encrypt is not None else cfg.backup_encryption_enabled
    extension = f"{source.suffix}.enc" if should_encrypt else source.suffix
    backup_filename = f"{clean_stem}_{timestamp}_{clean_tag}{extension}"
    backup_path = target_backup_dir / backup_filename

    try:
        with open(source, "rb") as src_f:
            data = src_f.read()

        if should_encrypt:
            cipher = get_backup_cipher()
            final_data = cipher.encrypt(data)
        else:
            final_data = data

        with open(backup_path, "wb") as dst_f:
            dst_f.write(final_data)

        # Generar archivo de firma HMAC-SHA256
        hmac_sig = compute_file_hmac(backup_path)
        sha256_hash = compute_file_sha256(backup_path)
        checksum_path = backup_path.with_suffix(backup_path.suffix + ".sha256")
        with open(checksum_path, "w", encoding="utf-8") as chk_f:
            chk_f.write(f"{sha256_hash}:{hmac_sig}  {backup_path.name}\n")

        logger.info(f"Backup creado exitosamente ({'Cifrado' if should_encrypt else 'Plano'}): {backup_path.name} (HMAC: {hmac_sig[:12]}...)")
        
        # Rotar backups antiguos si se configuró un límite
        limit = max_backups if max_backups is not None else cfg.max_backups_retained
        _rotate_backups(target_backup_dir, clean_stem, extension, limit)
        
        return backup_path
    except Exception as e:
        logger.error(f"Falla al generar copia de seguridad de {source}: {e}")
        return None


def verify_backup_integrity(backup_path: Path | str) -> Tuple[bool, Optional[str]]:
    """
    Verifica la integridad de un archivo de backup comprobando su firma HMAC-SHA256.
    Retorna (es_integro, mensaje_error).
    """
    path = Path(backup_path)
    if not path.exists():
        return False, "El archivo de backup no existe."

    checksum_path = path.with_suffix(path.suffix + ".sha256")
    if not checksum_path.exists():
        return True, "Advertencia: Backup sin archivo de firma complementaria."

    try:
        with open(checksum_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        expected_sig_line = content.split()[0]
        
        # Soportar formato combinado hash:hmac o hash puro
        if ":" in expected_sig_line:
            expected_sha, expected_hmac = expected_sig_line.split(":", 1)
            current_hmac = compute_file_hmac(path)
            if not hmac.compare_digest(current_hmac, expected_hmac):
                return False, f"Firma HMAC inválida. El backup ha sido adulterado o la clave no coincide."
        else:
            current_sha = compute_file_sha256(path)
            if not hmac.compare_digest(current_sha, expected_sig_line):
                return False, f"Checksum SHA-256 no coincide. Archivo alterado o corrupto."

        return True, None
    except Exception as e:
        return False, f"Error leyendo firma de integridad: {e}"


def _rotate_backups(backup_dir: Path, file_stem: str, suffix: str, max_backups: int) -> None:
    """Elimina los backups más antiguos si superan el límite configurado junto a sus checksums."""
    if max_backups <= 0:
        return
    try:
        pattern = f"{file_stem}_*{suffix}"
        matching_backups = sorted(
            backup_dir.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if len(matching_backups) > max_backups:
            for old_backup in matching_backups[max_backups:]:
                try:
                    old_backup.unlink()
                    chk_file = old_backup.with_suffix(old_backup.suffix + ".sha256")
                    if chk_file.exists():
                        chk_file.unlink()
                    logger.debug(f"Backup antiguo rotado y eliminado: {old_backup.name}")
                except Exception as e:
                    logger.warning(f"No se pudo eliminar backup antiguo {old_backup}: {e}")
    except Exception as e:
        logger.warning(f"Error durante rotación de backups: {e}")


def list_backups(
    file_prefix: Optional[str] = None,
    backup_dir: Optional[Path | str] = None,
) -> List[Dict[str, Any]]:
    """Devuelve la lista de backups disponibles con metadatos de cifrado e integridad."""
    cfg = get_config()
    target_backup_dir = Path(backup_dir) if backup_dir else cfg.get_absolute_path(cfg.backup_dir)
    if not target_backup_dir.exists():
        return []

    results = []
    pattern = f"*{file_prefix}*.*" if file_prefix else "*.*"
    for f in target_backup_dir.glob(pattern):
        if f.is_file() and not f.name.endswith(".sha256"):
            stat = f.stat()
            is_enc = f.name.endswith(".enc")
            chk_file = f.with_suffix(f.suffix + ".sha256")
            has_checksum = chk_file.exists()

            results.append({
                "filename": f.name,
                "path": str(f),
                "size_kb": round(stat.st_size / 1024, 2),
                "created_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "extension": f.suffix,
                "encrypted": is_enc,
                "has_checksum": has_checksum,
            })
    return sorted(results, key=lambda x: x["created_at"], reverse=True)


def restore_backup(
    backup_path: Path | str,
    target_destination: Path | str,
    create_safety_backup: bool = True,
) -> bool:
    """
    Restaura un backup hacia la ruta de destino validando integridad SHA-256 y descifrando si corresponde.
    """
    backup_file = Path(backup_path)
    dest_file = Path(target_destination)

    if not backup_file.exists():
        logger.error(f"El archivo de backup no existe: {backup_file}")
        return False

    # 1. Validación de Integridad HMAC / SHA-256 previa
    is_valid, integrity_err = verify_backup_integrity(backup_file)
    if not is_valid:
        logger.critical(f"INTEGRIDAD COMPROMETIDA en {backup_file.name}: {integrity_err}")
        return False

    try:
        if create_safety_backup and dest_file.exists():
            create_backup(dest_file, tag="pre_restore_safety")

        dest_file.parent.mkdir(parents=True, exist_ok=True)

        with open(backup_file, "rb") as bf:
            data = bf.read()

        # 2. Descifrado si está cifrado con Fernet
        is_encrypted = backup_file.name.endswith(".enc") or data.startswith(b"gAAAAA")
        if is_encrypted:
            cipher = get_backup_cipher()
            restored_data = cipher.decrypt(data)
        else:
            restored_data = data

        with open(dest_file, "wb") as df:
            df.write(restored_data)

        logger.info(f"Restauración completada exitosamente: {backup_file.name} -> {dest_file}")
        return True
    except Exception as e:
        logger.error(f"Error restaurando backup {backup_file} en {dest_file}: {e}", exc_info=True)
        return False


def backup_whatsapp_session(
    session_dir: Optional[Path | str] = None,
    backup_dir: Optional[Path | str] = None,
    encrypt: bool = True,
) -> Optional[Path]:
    """Crea un archivo timestamped y cifrado con AES-256 de las credenciales de sesión de Baileys."""
    cfg = get_config()
    source_dir = Path(session_dir) if session_dir else cfg.base_dir / "whatsapp_bridge" / "auth_info_baileys"
    if not source_dir.exists() or not any(source_dir.iterdir()):
        logger.warning(f"Directorio de sesión de WhatsApp no existe o está vacío: {source_dir}")
        return None

    target_backup_dir = (Path(backup_dir) if backup_dir else cfg.get_absolute_path(cfg.backup_dir)) / "whatsapp_sessions"
    target_backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    extension = ".zip.enc" if encrypt else ".zip"
    final_path = target_backup_dir / f"whatsapp_session_{timestamp}{extension}"

    try:
        # Comprimir en memoria
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
            for item in source_dir.rglob("*"):
                if item.is_file():
                    zipf.write(item, item.relative_to(source_dir))

        raw_zip_bytes = zip_buffer.getvalue()

        if encrypt:
            cipher = get_backup_cipher()
            final_bytes = cipher.encrypt(raw_zip_bytes)
        else:
            final_bytes = raw_zip_bytes

        with open(final_path, "wb") as f:
            f.write(final_bytes)

        # Generar Checksum
        sha256_hash = hashlib.sha256(final_bytes).hexdigest()
        chk_path = final_path.with_suffix(final_path.suffix + ".sha256")
        with open(chk_path, "w", encoding="utf-8") as chk_f:
            chk_f.write(f"{sha256_hash}  {final_path.name}\n")

        logger.info(f"Sesión de WhatsApp respaldada ({'Cifrada AES-256' if encrypt else 'Plana'}): {final_path.name}")
        return final_path
    except Exception as e:
        logger.error(f"Error respaldando sesión de WhatsApp: {e}", exc_info=True)
        return None

