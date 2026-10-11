"""
Nexo Analytics - Servicio de Auditoría y Trazabilidad Inmutable con Hash Chaining
Garantiza el no repudio y la detección de manipulaciones directas en base de datos mediante encadenamiento criptográfico SHA-256.
"""

from __future__ import annotations
import hashlib
import json
import re
import datetime
import threading
import hmac
from pathlib import Path
from typing import Optional, Any, Dict, List, Tuple

from sqlalchemy.orm import Session
from finance_app.db.models import AuditLog, User
from finance_app.config import get_config
from finance_app.logging_config import get_logger

logger = get_logger("audit_service")

GENESIS_HASH = "0" * 64
_audit_lock = threading.Lock()
_ANCHOR_LOG_PATH = Path("data") / "audit_anchors.log"


def _write_audit_anchor(entry: AuditLog) -> None:
    """Ancla el hash de auditoría en un archivo append-only externo firmado con HMAC."""
    try:
        cfg = get_config()
        secret = (cfg.app_secret_key or "NexoAuditAnchorSecret2026").encode("utf-8")
        payload = f"{entry.id}|{entry.timestamp.isoformat()}|{entry.entry_hash}"
        signature = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
        
        _ANCHOR_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_ANCHOR_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{payload}|{signature}\n")
    except Exception as e:
        logger.warning(f"No se pudo escribir el anclaje externo de auditoría: {e}")


def _mask_pii_data(data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Enmascara campos sensibles (teléfonos, emails, claves) antes de persistirlos en auditoría."""
    if not data or not isinstance(data, dict):
        return data

    masked = {}
    for k, v in data.items():
        k_lower = str(k).lower()
        if any(secret_term in k_lower for secret_term in ("password", "pwd", "token", "secret", "key")):
            masked[k] = "[REDACTED]"
        elif "phone" in k_lower or "telefono" in k_lower:
            v_str = str(v)
            if len(v_str) > 6:
                masked[k] = f"{v_str[:4]}****{v_str[-3:]}"
            else:
                masked[k] = "[MASKED_PHONE]"
        elif "email" in k_lower or "correo" in k_lower:
            v_str = str(v)
            if "@" in v_str:
                user_part, domain = v_str.split("@", 1)
                masked[k] = f"{user_part[:1]}***@{domain}"
            else:
                masked[k] = "[MASKED_EMAIL]"
        elif "name" in k_lower or "nombre" in k_lower:
            v_str = str(v)
            if len(v_str) > 2:
                masked[k] = f"{v_str[:2]}***{v_str[-1:]}"
            else:
                masked[k] = "[MASKED_NAME]"
        else:
            masked[k] = v
    return masked


def _compute_audit_hash(
    prev_hash: str,
    timestamp_str: str,
    username: str,
    action: str,
    entity_type: str,
    entity_id: Optional[str],
    old_data_json: Optional[str],
    new_data_json: Optional[str],
    ip_address: Optional[str],
) -> str:
    """Calcula el hash SHA-256 inmutable para la entrada actual encadenada con la anterior."""
    raw_payload = f"{prev_hash}|{timestamp_str}|{username}|{action}|{entity_type}|{entity_id or ''}|{old_data_json or ''}|{new_data_json or ''}|{ip_address or ''}"
    return hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()


def log_audit_event(
    session: Session,
    action: str,
    entity_type: str,
    entity_id: Optional[str | int] = None,
    user: Optional[User | Dict[str, Any] | str] = None,
    old_data: Optional[Dict[str, Any]] = None,
    new_data: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> AuditLog:
    """Registra una entrada inmutable en el log de auditoría con bloqueo atómico y anclaje externo."""
    user_id = None
    username = "system"

    if isinstance(user, User):
        user_id = user.id
        username = user.username
    elif isinstance(user, dict):
        user_id = user.get("id")
        username = user.get("username", "system")
    elif isinstance(user, str):
        username = user

    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    timestamp_str = now.isoformat()

    # Enmascaramiento de datos sensibles
    masked_old = _mask_pii_data(old_data)
    masked_new = _mask_pii_data(new_data)
    old_json = json.dumps(masked_old, default=str, ensure_ascii=False) if masked_old else None
    new_json = json.dumps(masked_new, default=str, ensure_ascii=False) if masked_new else None
    clean_entity_id = str(entity_id) if entity_id is not None else None

    with _audit_lock:
        # Obtener el hash de la última entrada para encadenar atómicamente
        last_entry = session.query(AuditLog).order_by(AuditLog.id.desc()).first()
        prev_hash = last_entry.entry_hash if (last_entry and last_entry.entry_hash) else GENESIS_HASH

        entry_hash = _compute_audit_hash(
            prev_hash=prev_hash,
            timestamp_str=timestamp_str,
            username=username,
            action=action.upper(),
            entity_type=entity_type,
            entity_id=clean_entity_id,
            old_data_json=old_json,
            new_data_json=new_json,
            ip_address=ip_address,
        )

        audit_entry = AuditLog(
            user_id=user_id,
            username=username,
            action=action.upper(),
            entity_type=entity_type,
            entity_id=clean_entity_id,
            old_data_json=old_json,
            new_data_json=new_json,
            ip_address=ip_address,
            prev_hash=prev_hash,
            entry_hash=entry_hash,
            timestamp=now,
        )
        session.add(audit_entry)
        session.flush()
        _write_audit_anchor(audit_entry)

    logger.debug(f"AuditLog [SHA-256 {entry_hash[:8]}]: [{username}] {action} en {entity_type} (ID: {clean_entity_id})")
    return audit_entry



def verify_audit_integrity(session: Session) -> Tuple[bool, int, Optional[str]]:
    """
    Verifica la integridad criptográfica de toda la cadena de auditoría desde el bloque génesis.
    Retorna (es_valido: bool, total_verificados: int, mensaje_error: Optional[str]).
    """
    entries = session.query(AuditLog).order_by(AuditLog.id.asc()).all()
    if not entries:
        return True, 0, "No hay registros de auditoría almacenados."

    expected_prev_hash = GENESIS_HASH

    for i, entry in enumerate(entries):
        # 1. Validar enlace de hash previo
        if entry.prev_hash != expected_prev_hash:
            return (
                False,
                i,
                f"Ruptura de cadena en registro ID {entry.id}: prev_hash no coincide con la entrada anterior (Esperado: {expected_prev_hash[:12]}..., Encontrado: {entry.prev_hash[:12] if entry.prev_hash else 'None'}...)",
            )

        # 2. Recalcular y validar hash de la entrada actual
        timestamp_str = entry.timestamp.isoformat() if entry.timestamp else ""
        recalculated_hash = _compute_audit_hash(
            prev_hash=entry.prev_hash or GENESIS_HASH,
            timestamp_str=timestamp_str,
            username=entry.username,
            action=entry.action,
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
            old_data_json=entry.old_data_json,
            new_data_json=entry.new_data_json,
            ip_address=entry.ip_address,
        )

        if recalculated_hash != entry.entry_hash:
            return (
                False,
                i,
                f"Manipulación de datos detectada en registro ID {entry.id}: el contenido no coincide con el hash criptográfico.",
            )

        expected_prev_hash = entry.entry_hash

    return True, len(entries), f"✓ Cadena de auditoría verificada íntegra ({len(entries)} eventos firmados criptográficamente)."


def get_audit_trail(
    session: Session,
    entity_type: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = 100,
) -> List[AuditLog]:
    """Consulta las entradas más recientes del registro de auditoría."""
    query = session.query(AuditLog).order_by(AuditLog.timestamp.desc())
    if entity_type and entity_type != "Todas":
        query = query.filter(AuditLog.entity_type == entity_type)
    if action and action != "Todas":
        query = query.filter(AuditLog.action == action.upper())
    return query.limit(limit).all()

