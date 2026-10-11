"""
Módulo de Autenticación Cloud Segura con Airtable y 2FA (Google Authenticator).

Características de Seguridad:
1. Zero Plaintext: Las contraseñas nunca se guardan en texto plano en Airtable (bcrypt con salt dinámico).
2. Secreto 2FA Protegido: Los secretos TOTP se cifran con AES-256-GCM antes de enviarse a Airtable.
3. Reseteo Manual desde Airtable: Si el administrador marca 'reset_generico', el usuario ingresa
   con la contraseña genérica y el sistema le exige revalidar con 2FA y definir nueva contraseña.
4. Recuperación con 2FA: Si el usuario olvida su contraseña, puede reestablecerla demostrando
   posesión de su segundo factor de autenticación (Google Authenticator).
"""

import io
import json
import re
import time
from typing import Any, Dict, List, Optional, Tuple
import urllib.parse

import bcrypt
import pyotp
import qrcode
import requests

from finance_app.config import get_config
from finance_app.db.crypto import encrypt_field, decrypt_field
from finance_app.logging_config import get_logger

logger = get_logger("airtable_auth")

_EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+$"
)


def is_valid_email(email: str) -> bool:
    """
    Valida de forma estricta y formal el formato de un correo electrónico.
    Exige estructura válida usuario@dominio.extension (ej: usuario@empresa.com).
    """
    if not email or not isinstance(email, str):
        return False
    clean = email.strip()
    if len(clean) < 5 or len(clean) > 254:
        return False
    if " " in clean or ".." in clean:
        return False
    if not _EMAIL_REGEX.match(clean):
        return False
    # Verificar que el TLD (extensión final) tenga al menos 2 letras
    parts = clean.split(".")
    tld = parts[-1]
    if len(tld) < 2 or not tld.isalpha():
        return False
    return True


def hash_password(plain_password: str) -> str:
    """Genera un hash seguro irreversible con bcrypt y 12 rondas de sal."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def check_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica si la contraseña coincide con el hash almacenado en Airtable."""
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception as e:
        logger.warning(f"Error verificando hash bcrypt: {e}")
        return False


def validate_password_policy(password: str) -> Tuple[bool, str]:
    """
    Valida los 5 requisitos de seguridad de la contraseña idéntico a Login.jsx:
    1. Entre 6 y 20 caracteres
    2. Al menos una letra minúscula (a-z)
    3. Al menos una letra mayúscula (A-Z)
    4. Al menos un número (0-9)
    5. Al menos un caracter especial (!, @, #, $, etc.)
    """
    if not (6 <= len(password) <= 20):
        return False, "La contraseña debe tener entre 6 y 20 caracteres."
    if not any(c.islower() for c in password):
        return False, "La contraseña debe incluir al menos una letra minúscula (a-z)."
    if not any(c.isupper() for c in password):
        return False, "La contraseña debe incluir al menos una letra mayúscula (A-Z)."
    if not any(c.isdigit() for c in password):
        return False, "La contraseña debe incluir al menos un número (0-9)."
    if not any(c in "!@#$%^&*()_+-=[]{};':\"\\|,.<>?/~`" for c in password):
        return False, "La contraseña debe incluir al menos un caracter especial (!, @, #, $, etc.)."
    return True, ""


def validate_registration_fields(nombre: str, email: str, password: str, repetir: str) -> Optional[str]:
    """
    Valida los campos del formulario de registro idéntico a validarRegistro() de Login.jsx:
    - Nombre: al menos 3 caracteres (hasta 40)
    - Email: formato válido con expresión regular
    - Contraseña: 5 requisitos de seguridad (longitud 6-20, minúscula, mayúscula, número, especial)
    - Repetir contraseña: coincidencia exacta con password
    Retorna el mensaje de error o None si es completamente válido.
    """
    clean_nombre = (nombre or "").strip()
    clean_email = (email or "").strip()

    if len(clean_nombre) < 3:
        return "El nombre debe contener al menos 3 caracteres."
    if len(clean_nombre) > 40:
        return "El nombre no puede superar los 40 caracteres."
    if not is_valid_email(clean_email):
        return "Ingresa un correo electrónico con formato válido."

    val_ok, val_err = validate_password_policy(password)
    if not val_ok:
        return val_err

    if password != repetir:
        return "Las contraseñas no coinciden."

    return None



def generate_totp_secret() -> str:
    """Genera una semilla aleatoria en Base32 para Google Authenticator."""
    return pyotp.random_base32()


def get_totp_uri(secret: str, email: str) -> str:
    """Genera la URI estándar otpauth:// compatible con Google Authenticator."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name="Consultora CRM")


def generate_qr_code_image_bytes(uri: str) -> bytes:
    """Genera una imagen PNG del código QR para escanear en Google Authenticator."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=3,
    )
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def verify_totp_code(secret: str, code: str) -> bool:
    """Verifica el código de 6 dígitos con ventana de tolerancia de ±30 segundos."""
    if not secret or not code:
        return False
    clean_code = str(code).strip().replace(" ", "").replace("-", "")
    if len(clean_code) != 6 or not clean_code.isdigit():
        return False
    try:
        totp = pyotp.TOTP(secret)
        return bool(totp.verify(clean_code, valid_window=1))
    except Exception as e:
        logger.warning(f"Error verificando TOTP: {e}")
        return False


def _get_airtable_headers() -> Dict[str, str]:
    cfg = get_config()
    return {
        "Authorization": f"Bearer {cfg.airtable_api_key}",
        "Content-Type": "application/json",
    }


def _get_airtable_url(record_id: Optional[str] = None) -> str:
    cfg = get_config()
    encoded_table = urllib.parse.quote(cfg.airtable_table_name)
    base = f"https://api.airtable.com/v0/{cfg.airtable_base_id}/{encoded_table}"
    return f"{base}/{record_id}" if record_id else base


_USERS_CACHE: Dict[str, Any] = {"data": [], "timestamp": 0.0}


def _is_truthy(val: Any) -> bool:
    """Evalúa con tolerancia valores booleanos procedentes de columnas Checkbox o Single-Select de Airtable."""
    if val is None:
        return False
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return val != 0
    if isinstance(val, str):
        return val.strip().lower() in ("true", "1", "si", "sí", "activo", "habilitado", "yes")
    return bool(val)


def fetch_all_users(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """Descarga los registros de usuarios desde la tabla de Airtable con caché de alta respuesta."""
    cfg = get_config()
    if not cfg.airtable_api_key:
        return []

    now = time.time()
    if not force_refresh and (now - _USERS_CACHE["timestamp"] < 5.0) and _USERS_CACHE["data"]:
        return _USERS_CACHE["data"]

    url = _get_airtable_url()
    headers = _get_airtable_headers()
    records: List[Dict[str, Any]] = []
    offset = None

    try:
        while True:
            params = {}
            if offset:
                params["offset"] = offset
            resp = requests.get(url, headers=headers, params=params, timeout=12)
            if resp.status_code != 200:
                logger.error(f"Error leyendo Airtable ({resp.status_code}): {resp.text[:150]}")
                break
            data = resp.json()
            records.extend(data.get("records", []))
            offset = data.get("offset")
            if not offset:
                break
    except Exception as e:
        logger.error(f"Fallo de conexión con Airtable: {e}")
        return _USERS_CACHE["data"] if _USERS_CACHE["data"] else []

    # Normalizar usuarios
    users = []
    for r in records:
        f = r.get("fields", {})
        email = str(f.get("email", "")).strip().lower()
        if not email:
            continue
        users.append({
            "record_id": r["id"],
            "email": email,
            "nombre": f.get("nombre", email.split("@")[0]),
            "rol": str(f.get("rol", "viewer")).lower(),
            "password_hash": f.get("password_hash", ""),
            "totp_secret_encrypted": f.get("totp_secret", ""),
            "totp_enabled": _is_truthy(f.get("totp_enabled")),
            "reset_generico": _is_truthy(f.get("reset_generico")),
            "activo": _is_truthy(f.get("activo", True)),
        })

    _USERS_CACHE["data"] = users
    _USERS_CACHE["timestamp"] = now
    return users


def find_user_by_email(email: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
    """Busca un usuario por su dirección de correo en Airtable."""
    if not email:
        return None
    normalized_email = email.strip().lower()
    users = fetch_all_users(force_refresh=force_refresh)
    for u in users:
        if u["email"].lower() == normalized_email:
            return u
    return None


def update_airtable_user(record_id: str, fields: Dict[str, Any]) -> bool:
    """Actualiza campos específicos de un registro en Airtable e invalida la caché."""
    url = _get_airtable_url(record_id)
    headers = _get_airtable_headers()

    # Formatear campos booleanos de forma compatible con Checkbox y Single-Select de Airtable
    clean_fields: Dict[str, Any] = {}
    for k, v in fields.items():
        if k in ("totp_enabled", "reset_generico", "activo"):
            if v is True or (isinstance(v, str) and v.lower() in ("true", "1", "si", "sí", "yes")):
                clean_fields[k] = "true"
            elif v is False or (isinstance(v, str) and v.lower() in ("false", "0", "no")):
                clean_fields[k] = None
            else:
                clean_fields[k] = v
        else:
            clean_fields[k] = v

    try:
        resp = requests.patch(url, headers=headers, json={"fields": clean_fields, "typecast": True}, timeout=10)
        if resp.status_code in (200, 201):
            _USERS_CACHE["timestamp"] = 0.0
            return True
        logger.error(f"Error actualizando registro {record_id} en Airtable: {resp.status_code} - {resp.text[:150]}")
        return False
    except Exception as e:
        logger.error(f"Excepción actualizando Airtable: {e}")
        return False


def create_airtable_user(
    email: str,
    nombre: str,
    password: str,
    rol: str = "closer",
    activo: bool = True,
    reset_generico: bool = False,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Crea un nuevo usuario en Airtable con contraseña cifrada (bcrypt)
    y semilla 2FA protegida con AES-256-GCM.
    Si es el primer usuario del sistema, se le asigna rol 'admin'.
    """
    clean_nombre = nombre.strip()
    if len(clean_nombre) < 3:
        return False, "El nombre debe contener al menos 3 caracteres.", None
    if len(clean_nombre) > 40:
        return False, "El nombre no puede superar los 40 caracteres.", None

    clean_email = email.strip().lower()
    if not clean_email or not is_valid_email(clean_email):
        return False, "Ingresa un correo electrónico con formato válido.", None

    existing = find_user_by_email(clean_email, force_refresh=True)
    if existing:
        return False, f"El correo {clean_email} ya se encuentra registrado.", None

    if password:
        val_ok, val_err = validate_password_policy(password)
        if not val_ok:
            return False, val_err, None

    # Control estricto de administrador único: Solamente se permite 1 admin en todo el sistema
    current_users = fetch_all_users()
    existing_admins = [u for u in current_users if str(u.get("rol", "")).lower() == "admin"]

    if len(existing_admins) == 0:
        # Si aún no hay administrador registrado, la primera cuenta es el Administrador Único
        effective_role = "admin"
    else:
        # Ya existe un administrador registrado. Se bloquea cualquier intento de crear otro admin
        if str(rol).lower() == "admin":
            return False, "🚫 Operación denegada por ciberseguridad: Ya existe un Administrador registrado. Solamente se permite un (1) administrador único en el sistema.", None
        effective_role = rol.lower()

    pwd_hash = hash_password(password) if password else ""
    raw_totp_secret = generate_totp_secret()
    encrypted_secret = encrypt_field(raw_totp_secret)

    fields: Dict[str, Any] = {
        "email": clean_email,
        "nombre": nombre.strip() or clean_email.split("@")[0],
        "rol": effective_role,
        "password_hash": pwd_hash,
        "totp_secret": encrypted_secret,
    }
    if activo:
        fields["activo"] = "true"
    if reset_generico:
        fields["reset_generico"] = "true"
    # totp_enabled se omite al crear para evitar el error 422 si la columna es Single Select

    url = _get_airtable_url()
    headers = _get_airtable_headers()
    try:
        resp = requests.post(url, headers=headers, json={"fields": fields, "typecast": True}, timeout=12)
        if resp.status_code in (200, 201):
            _USERS_CACHE["timestamp"] = 0.0
            data = resp.json()
            user_data = {
                "record_id": data["id"],
                "email": clean_email,
                "nombre": fields["nombre"],
                "rol": effective_role,
                "totp_secret_raw": raw_totp_secret,
                "totp_enabled": False,
                "reset_generico": reset_generico,
                "activo": activo,
            }
            return True, "Usuario creado exitosamente.", user_data
        return False, f"Error de Airtable: {resp.status_code} - {resp.text[:120]}", None
    except Exception as e:
        return False, f"Error de conexión con Airtable: {e}", None


def delete_airtable_user(
    record_id: str,
    target_user: Dict[str, Any],
    current_admin: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str]:
    """
    Elimina una cuenta de usuario en Airtable.
    REGLA DE CIBERSEGURIDAD CRÍTICA:
    - Las cuentas con rol 'admin' NO pueden eliminarse bajo ninguna circunstancia.
    - Un administrador no puede eliminarse a sí mismo.
    """
    target_role = str(target_user.get("rol") or target_user.get("role", "")).lower()
    if target_role == "admin":
        return False, "🚫 Operación denegada por ciberseguridad: Las cuentas con rol Administrador están protegidas contra eliminación."

    if current_admin:
        target_email = str(target_user.get("email", "")).strip().lower()
        admin_email = str(current_admin.get("email") or current_admin.get("username", "")).strip().lower()
        if target_email and target_email == admin_email:
            return False, "🚫 Operación denegada: No puedes eliminar tu propia cuenta de administrador."

    url = _get_airtable_url(record_id)
    headers = _get_airtable_headers()
    try:
        resp = requests.delete(url, headers=headers, timeout=10)
        if resp.status_code in (200, 204):
            _USERS_CACHE["timestamp"] = 0.0
            return True, f"Cuenta '{target_user.get('email')}' eliminada permanentemente de Airtable."
        return False, f"Error al eliminar en Airtable: {resp.status_code} - {resp.text[:120]}"
    except Exception as e:
        return False, f"Error de conexión con Airtable: {e}"


def admin_reset_user_password(
    record_id: str,
    email: str,
    generic_password: str = "Consultora2026!",
) -> Tuple[bool, str]:
    """
    Reestablece la contraseña de cualquier usuario a la clave genérica de rescate
    y marca 'reset_generico = True'.
    Al ingresar su email en el portal, el usuario verá inmediatamente el cartel
    indicando que su contraseña fue reestablecida y deberá definir una nueva.
    """
    pwd_hash = hash_password(generic_password)
    ok = update_airtable_user(record_id, {
        "password_hash": pwd_hash,
        "reset_generico": True,
    })
    if ok:
        _USERS_CACHE["timestamp"] = 0.0
        return True, f"Contraseña de '{email}' reestablecida a la clave genérica ({generic_password}). El usuario verá el aviso al colocar su correo."
    return False, "Error al comunicar el reestablecimiento con Airtable."


def admin_update_user_account(
    record_id: str,
    fields: Dict[str, Any],
    target_user: Dict[str, Any],
    current_admin: Dict[str, Any],
) -> Tuple[bool, str]:
    """
    Actualiza rol o estado de una cuenta.
    Impide que un administrador degrade su propio rol o desactive su propia cuenta.
    """
    target_email = str(target_user.get("email", "")).strip().lower()
    admin_email = str(current_admin.get("email") or current_admin.get("username", "")).strip().lower()
    is_self = target_email and (target_email == admin_email)

    if is_self:
        if "rol" in fields and str(fields["rol"]).lower() != "admin":
            return False, "🚫 No puedes revocar tu propio rol de Administrador."
        if "activo" in fields and not fields["activo"]:
            return False, "🚫 No puedes suspender tu propia cuenta de Administrador."
    else:
        # Si intentan elevar a otro usuario a admin, verificar si ya existe un admin
        if "rol" in fields and str(fields["rol"]).lower() == "admin":
            if str(target_user.get("rol", "")).lower() != "admin":
                current_users = fetch_all_users()
                existing_admins = [u for u in current_users if str(u.get("rol", "")).lower() == "admin"]
                if len(existing_admins) >= 1:
                    return False, "🚫 Operación denegada: Solamente se permite un (1) Administrador único en el sistema. No se pueden crear administradores adicionales."

    ok = update_airtable_user(record_id, fields)
    if ok:
        _USERS_CACHE["timestamp"] = 0.0
        return True, "Cuenta actualizada correctamente en Airtable."
    return False, "Error al actualizar la cuenta en Airtable."



def authenticate_user_with_airtable(
    email: str,
    password: str,
    totp_code: Optional[str] = None,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Valida las credenciales contra Airtable contemplando:
    1. Si reset_generico está activo: permite ingreso con la clave genérica de rescate.
    2. Si las credenciales son válidas y 2FA está activo: exige código de Google Authenticator.
    3. Si 2FA aún no fue configurado: solicita enrolamiento obligatorio del código QR.
    """
    clean_email = email.strip().lower() if email else ""

    if not clean_email or not is_valid_email(clean_email):
        return False, "Ingresa un correo electrónico con formato válido.", None

    cfg = get_config()
    user = find_user_by_email(clean_email)
    if not user:
        return False, "Usuario o correo no encontrado.", None

    if not user.get("activo"):
        return False, "La cuenta se encuentra inactiva o suspendida. Contacte al administrador.", None

    # 1. Comprobación del botón de rescate manual desde Airtable
    if user.get("reset_generico"):
        if password == cfg.airtable_generic_password:
            # Clave genérica válida -> Requiere cambio forzoso de clave
            return True, "RESET_GENERICO_ACTIVO", user
        # Si no coincide la genérica, se evalúa si coincide su clave normal

    # 2. Comprobación de contraseña normal (bcrypt)
    stored_hash = user.get("password_hash")
    if not stored_hash or not check_password(password, stored_hash):
        if user.get("reset_generico"):
            return False, "Contraseña incorrecta (la cuenta tiene habilitado reseteo genérico en Airtable).", None
        return False, "Contraseña incorrecta.", None

    # 3. Comprobación de 2FA (Google Authenticator)
    if not user.get("totp_enabled") or not user.get("totp_secret_encrypted"):
        # Requiere enrolar 2FA por primera vez
        return True, "SETUP_2FA_REQUERIDO", user

    # Si ya tiene 2FA habilitado, verificar código
    if not totp_code:
        return False, "REQUIERE_2FA_CODE", user

    try:
        raw_secret = decrypt_field(user.get("totp_secret_encrypted"))
    except Exception as e:
        logger.error(f"Error descifrando secreto TOTP de {email}: {e}")
        return False, "Error criptográfico de seguridad en 2FA. Contacte al administrador.", None

    if not verify_totp_code(raw_secret, totp_code):
        return False, "Código 2FA de Google Authenticator inválido o expirado.", None

    return True, "AUTENTICADO", user


def activate_user_2fa(
    record_id: str,
    raw_secret: str,
    totp_code: str,
    new_password: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Confirma el enrolamiento del QR en Google Authenticator.
    Cifra el secreto en AES-256-GCM y activa el 2FA en Airtable.
    Opcionalmente actualiza la contraseña y apaga 'reset_generico'.
    """
    if not verify_totp_code(raw_secret, totp_code):
        return False, "El código de 6 dígitos no coincide. Verifique la hora de su teléfono y reintente."

    encrypted_secret = encrypt_field(raw_secret)
    updates: Dict[str, Any] = {
        "totp_secret": encrypted_secret,
        "totp_enabled": True,
        "reset_generico": False,
    }
    if new_password:
        val_ok, val_err = validate_password_policy(new_password)
        if not val_ok:
            return False, val_err
        updates["password_hash"] = hash_password(new_password)

    ok = update_airtable_user(record_id, updates)
    if ok:
        return True, "2FA activado y credenciales guardadas exitosamente."
    return False, "No fue posible actualizar el registro en Airtable."


def reset_password_via_2fa(
    email: str,
    totp_code: str,
    new_password: str,
) -> Tuple[bool, str]:
    """
    Permite al usuario reestablecer su contraseña olvidada demostrando
    su identidad mediante el código 2FA de Google Authenticator.
    """
    clean_email = email.strip().lower() if email else ""
    if not clean_email or not is_valid_email(clean_email):
        return False, "Ingresa un correo electrónico con formato válido."

    user = find_user_by_email(clean_email)
    if not user:
        return False, "Correo no encontrado."

    if not user.get("totp_secret_encrypted"):
        return False, "Este usuario no tiene configurado el 2FA de Google Authenticator."

    try:
        raw_secret = decrypt_field(user["totp_secret_encrypted"])
    except Exception as e:
        return False, f"Error de descifrado 2FA: {e}"

    if not verify_totp_code(raw_secret, totp_code):
        return False, "Código 2FA incorrecto o expirado."

    val_ok, val_err = validate_password_policy(new_password)
    if not val_ok:
        return False, val_err

    new_hash = hash_password(new_password)
    ok = update_airtable_user(user["record_id"], {
        "password_hash": new_hash,
        "reset_generico": False,
    })
    if ok:
        return True, "Contraseña reestablecida correctamente. Ya puede iniciar sesión."
    return False, "Fallo al comunicar con Airtable."


# =========================================================================
# BÓVEDA DE SESIÓN CIFRADA CLIENTE (SESSIONSTORAGE & LOCALSTORAGE)
# =========================================================================
_LOGIN_ATTEMPTS: Dict[str, List[float]] = {}
_LOCKOUT_CACHE: Dict[str, float] = {}


def check_login_rate_limit(
    identifier: str,
    max_attempts: int = 5,
    window_seconds: int = 600,
    lockout_duration: int = 900,
) -> Tuple[bool, int]:
    """
    Control de fuerza bruta (Anti-Brute Force Protection):
    Si se registran más de max_attempts fallidos en window_seconds,
    bloquea intentos por lockout_duration (15 minutos).
    Retorna (permitido: bool, segundos_restantes: int).
    """
    clean_id = identifier.strip().lower()
    now = time.time()

    # Verificar si está bloqueado activamente
    if clean_id in _LOCKOUT_CACHE:
        locked_until = _LOCKOUT_CACHE[clean_id]
        if now < locked_until:
            remaining = int(locked_until - now)
            return False, remaining
        else:
            del _LOCKOUT_CACHE[clean_id]
            _LOGIN_ATTEMPTS.pop(clean_id, None)

    # Limpiar intentos fuera de la ventana
    attempts = [t for t in _LOGIN_ATTEMPTS.get(clean_id, []) if (now - t) < window_seconds]
    _LOGIN_ATTEMPTS[clean_id] = attempts

    if len(attempts) >= max_attempts:
        _LOCKOUT_CACHE[clean_id] = now + lockout_duration
        logger.warning(f"Cuenta/IP {clean_id} bloqueada por 15 minutos tras {len(attempts)} intentos fallidos.")
        return False, lockout_duration

    return True, 0


def record_failed_login(identifier: str) -> None:
    """Registra un intento de login fallido."""
    clean_id = identifier.strip().lower()
    now = time.time()
    if clean_id not in _LOGIN_ATTEMPTS:
        _LOGIN_ATTEMPTS[clean_id] = []
    _LOGIN_ATTEMPTS[clean_id].append(now)


def clear_failed_logins(identifier: str) -> None:
    """Limpia los intentos fallidos tras un inicio de sesión exitoso."""
    clean_id = identifier.strip().lower()
    _LOGIN_ATTEMPTS.pop(clean_id, None)
    _LOCKOUT_CACHE.pop(clean_id, None)


def create_encrypted_client_session_token(user_dict: dict, max_age_seconds: int = 86400) -> str:
    """
    Genera un token de sesión sellado y cifrado militarmente con AES-256-GCM.
    Este token es el que se almacena en el sessionStorage y localStorage del navegador.
    Ningún dato sensible (contraseñas, emails en texto plano, etc.) queda expuesto.
    """
    now = time.time()
    payload = {
        "id": user_dict.get("id") or user_dict.get("record_id"),
        "email": user_dict.get("email"),
        "nombre": user_dict.get("nombre") or user_dict.get("full_name"),
        "rol": user_dict.get("rol") or user_dict.get("role", "closer"),
        "issued_at": now,
        "expires_at": now + max_age_seconds,
        "token_version": 2,
    }
    raw_json = json.dumps(payload, separators=(",", ":"))
    # Cifrado AES-256-GCM Fail-Closed con Nonce aleatorio de 96 bits
    encrypted_token = encrypt_field(raw_json)
    return str(encrypted_token)


def verify_encrypted_client_session_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Descifra y valida la autenticidad e integridad del token de sesión almacenado en el cliente.
    Si el token fue alterado, expiró o no descifra, retorna None impidiendo el acceso.
    """
    if not token or not token.startswith("aesgcm:"):
        return None

    try:
        decrypted_json = decrypt_field(token)
        if not decrypted_json:
            return None
        payload = json.loads(decrypted_json)
    except Exception as e:
        logger.warning(f"Intento de manipulación de sesión en storage: {e}")
        return None

    # Validar caducidad temporal
    now = time.time()
    if now > payload.get("expires_at", 0):
        logger.info(f"Sesión en almacenamiento expirada para {payload.get('email')}")
        return None

    return {
        "id": payload.get("id"),
        "username": payload.get("email"),
        "full_name": payload.get("nombre"),
        "role": payload.get("rol", "closer"),
        "email": payload.get("email"),
        "must_change_password": False,
        "last_activity": now,
        "session_source": "encrypted_vault",
    }

