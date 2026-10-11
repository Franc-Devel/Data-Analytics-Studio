"""
Nexo Analytics - Módulo Criptográfico de Cifrado a Nivel de Campo (Field-Level Encryption)
Proporciona cifrado autenticado auténtico AES-256-GCM (NIST SP 800-38D), TypeDecorators para SQLAlchemy
y Blind Index (HMAC-SHA256) para búsquedas exactas e indexación en base de datos.
"""

from __future__ import annotations
import base64
import hmac
import hashlib
import os
import re
from typing import Optional, Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from sqlalchemy import types

from finance_app.config import get_config
from finance_app.logging_config import get_logger

logger = get_logger("crypto")

_CRYPTO_SALT = b"NexoAnalytics_AES256GCM_Field_Salt_2026"
_BLIND_INDEX_SALT = b"NexoAnalytics_Blind_Index_Salt_2026"
_AES_PREFIX = "aesgcm:"


def _derive_aes256_key(secret_str: str) -> bytes:
    """Deriva una clave de 256 bits (32 bytes) para AES-256-GCM utilizando PBKDF2-HMAC-SHA256."""
    if not secret_str:
        secret_str = "DefaultNexoAnalyticsDevFieldKey2026!ChangeInProd"

    # Si ya es una clave de 32 bytes codificada en base64 url-safe
    try:
        raw_b64 = secret_str.strip().encode("utf-8")
        decoded = base64.urlsafe_b64decode(raw_b64)
        if len(decoded) == 32:
            return decoded
    except Exception:
        pass

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_CRYPTO_SALT,
        iterations=100_000,
    )
    return kdf.derive(secret_str.encode("utf-8"))


def get_aesgcm_cipher() -> AESGCM:
    """Obtiene el motor de cifrado simétrico AES-256-GCM."""
    cfg = get_config()
    secret = cfg.app_encryption_key or cfg.app_secret_key
    key = _derive_aes256_key(secret)
    return AESGCM(key)


def encrypt_field(plaintext: Optional[str]) -> Optional[str]:
    """
    Cifra un valor de texto plano con AES-256-GCM y nonce de 96 bits.
    Retorna una cadena con prefijo 'aesgcm:<base64>'.
    FAIL CLOSED: Si ocurre un error, levanta una excepción impidiendo la persistencia en texto plano.
    """
    if plaintext is None or plaintext == "":
        return plaintext

    try:
        aesgcm = get_aesgcm_cipher()
        nonce = os.urandom(12)  # Nonce estándar de 96 bits para GCM
        data = plaintext.encode("utf-8")
        ciphertext = aesgcm.encrypt(nonce, data, None)
        payload = base64.urlsafe_b64encode(nonce + ciphertext).decode("utf-8")
        return f"{_AES_PREFIX}{payload}"
    except Exception as e:
        logger.critical(f"Falla crítica en cifrado AES-256-GCM: {e}", exc_info=True)
        raise RuntimeError(f"Error de seguridad: No se pudo cifrar el dato confidencial. Operación abortada.") from e


def decrypt_field(ciphertext: Optional[str]) -> Optional[str]:
    """
    Descifra una cadena protegida con AES-256-GCM retornando el texto plano original.
    Soporta también tokens legados Fernet para compatibilidad de migración.
    """
    if ciphertext is None or ciphertext == "":
        return ciphertext

    # Si tiene el prefijo de AES-256-GCM
    if isinstance(ciphertext, str) and ciphertext.startswith(_AES_PREFIX):
        raw_b64 = ciphertext[len(_AES_PREFIX):]
        try:
            raw_bytes = base64.urlsafe_b64decode(raw_b64.encode("utf-8"))
            if len(raw_bytes) < 28:  # 12 nonce + 16 tag mínimo
                return ciphertext
            nonce = raw_bytes[:12]
            actual_ciphertext = raw_bytes[12:]
            aesgcm = get_aesgcm_cipher()
            decrypted = aesgcm.decrypt(nonce, actual_ciphertext, None)
            return decrypted.decode("utf-8")
        except Exception as e:
            logger.error(f"Error descifrando campo AES-256-GCM: {e}")
            return ciphertext

    # Compatibilidad con tokens legacy Fernet (inician con gAAAAA)
    if isinstance(ciphertext, str) and ciphertext.startswith("gAAAAA"):
        try:
            from cryptography.fernet import Fernet
            cfg = get_config()
            secret = cfg.app_encryption_key or cfg.app_secret_key
            kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=b"NexoAnalytics_Field_Encryption_Salt_2026", iterations=100_000)
            f_key = base64.urlsafe_b64encode(kdf.derive(secret.encode("utf-8")))
            f = Fernet(f_key)
            return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except Exception:
            return ciphertext

    # No cifrado
    return ciphertext


def compute_blind_index(raw_value: Optional[str], is_phone: bool = False) -> Optional[str]:
    """
    Calcula un HMAC-SHA256 normalizado ('Blind Index') sobre un campo sensible (teléfono, email, CUIT).
    Permite búsquedas exactas e indexación en base de datos sin descifrar registros.
    """
    if not raw_value:
        return None

    cfg = get_config()
    secret = (cfg.blind_index_key or cfg.app_secret_key or "NexoBlindIndexKey2026").encode("utf-8")

    # Normalización del valor
    if is_phone:
        normalized = re.sub(r"\D", "", str(raw_value))
    else:
        normalized = str(raw_value).strip().lower()

    if not normalized:
        return None

    return hmac.new(secret, normalized.encode("utf-8"), hashlib.sha256).hexdigest()


def compute_name_token_hashes(raw_name: Optional[str], raw_company: Optional[str] = None) -> set[str]:
    """Devuelve hashes HMAC únicos de las palabras buscables de nombre y empresa."""
    combined = f"{raw_name or ''} {raw_company or ''}".strip()
    words = re.findall(r"\w+", combined.lower())
    return {
        token
        for word in words
        if len(word) >= 2
        for token in [compute_blind_index(word, is_phone=False)]
        if token
    }


def compute_name_tokens_index(raw_name: Optional[str], raw_company: Optional[str] = None) -> Optional[str]:
    """
    Tokeniza un nombre y/o razón social en palabras (>= 2 caracteres) y genera
    un índice de tokens HMAC-SHA256 delimitado por comas para búsqueda SQL rápida.
    """
    tokens = compute_name_token_hashes(raw_name, raw_company)
    if not tokens:
        return None
    return "," + ",".join(sorted(tokens)) + ","


def compute_phone_token_hashes(raw_phone: Optional[str]) -> set[str]:
    """Devuelve hashes HMAC de los fragmentos de teléfono admitidos por la búsqueda."""
    digits = re.sub(r"\D", "", str(raw_phone or ""))
    if len(digits) < 4:
        return set()
    values = {digits, digits[-4:]}
    if len(digits) >= 8:
        values.add(digits[-8:])
    values.update(digits[i:i + 4] for i in range(len(digits) - 3))
    return {
        token
        for value in values
        for token in [compute_blind_index(value, is_phone=True)]
        if token
    }


def compute_phone_tokens_index(raw_phone: Optional[str]) -> Optional[str]:
    """
    Calcula tokens ciegos HMAC de subcadenas numéricas relevantes (teléfono completo,
    sufijo 8, sufijo 4 y ventanas de 4 dígitos) para búsquedas SQL por fragmento.
    """
    tokens = compute_phone_token_hashes(raw_phone)
    return "," + ",".join(sorted(tokens)) + "," if tokens else None


# =========================================================================
# SQLAlchemy TypeDecorators para Cifrado Transparente
# =========================================================================

class EncryptedString(types.TypeDecorator):
    """Tipo SQLAlchemy que cifra transparentemente cadenas String(length) con AES-256-GCM."""
    impl = types.String(512)
    cache_ok = True

    def process_bind_param(self, value: Optional[str], dialect: Any) -> Optional[str]:
        if value is None:
            return None
        return encrypt_field(str(value))

    def process_result_value(self, value: Optional[str], dialect: Any) -> Optional[str]:
        if value is None:
            return None
        return decrypt_field(value)


class EncryptedText(types.TypeDecorator):
    """Tipo SQLAlchemy que cifra transparentemente campos Text con AES-256-GCM."""
    impl = types.Text
    cache_ok = True

    def process_bind_param(self, value: Optional[str], dialect: Any) -> Optional[str]:
        if value is None:
            return None
        return encrypt_field(str(value))

    def process_result_value(self, value: Optional[str], dialect: Any) -> Optional[str]:
        if value is None:
            return None
        return decrypt_field(value)
