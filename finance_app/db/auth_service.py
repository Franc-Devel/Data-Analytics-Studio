"""
Nexo Analytics - Servicio de Autenticación, Hashing y Control de Acceso (RBAC)
Gestiona usuarios, contraseñas seguras con bcrypt, bloqueo por fuerza bruta y políticas corporativas.
"""

from __future__ import annotations
import datetime
import re
import secrets
from typing import Optional, List, Dict, Any, Tuple

import bcrypt
from sqlalchemy.orm import Session

from finance_app.db.models import User
from finance_app.db.session import get_db_session, init_db
from finance_app.db.audit_service import log_audit_event
from finance_app.config import get_config
from finance_app.logging_config import get_logger

logger = get_logger("auth_service")

# Constantes de Política de Seguridad
MAX_FAILED_LOGIN_ATTEMPTS = 5
ACCOUNT_LOCKOUT_MINUTES = 15
MIN_PASSWORD_LENGTH = 12

# Definición de Permisos por Rol
ROLE_PERMISSIONS: Dict[str, List[str]] = {
    "admin": [
        "view_all",
        "edit_all",
        "manage_users",
        "manage_rules",
        "view_audit_logs",
        "manage_backups",
        "export_data",
        "import_data",
        "send_whatsapp",
    ],
    "manager": [
        "view_all",
        "edit_all",
        "manage_rules",
        "export_data",
        "import_data",
        "send_whatsapp",
    ],
    "closer": [
        "view_assigned",
        "edit_assigned",
        "create_customer",
        "create_opportunity",
        "create_task",
        "send_whatsapp",
    ],
    "viewer": [
        "view_all",
    ],
}


def validate_password_strength(password: str) -> Tuple[bool, Optional[str]]:
    """
    Valida la fortaleza de la contraseña según estándares corporativos (OWASP / NIST):
    - Mínimo 12 caracteres
    - Al menos una mayúscula y una minúscula
    - Al menos un dígito
    - Al menos un símbolo o carácter especial
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres."
    if not re.search(r"[A-Z]", password):
        return False, "La contraseña debe incluir al menos una letra mayúscula (A-Z)."
    if not re.search(r"[a-z]", password):
        return False, "La contraseña debe incluir al menos una letra minúscula (a-z)."
    if not re.search(r"[0-9]", password):
        return False, "La contraseña debe incluir al menos un número (0-9)."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "La contraseña debe incluir al menos un carácter especial (!@#$%^&*...)."
    return True, None


def hash_password(plain_password: str) -> str:
    """Genera un hash seguro utilizando bcrypt con salt automático de 12 rondas."""
    pwd_bytes = plain_password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica si una contraseña en texto plano coincide con el hash almacenado."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception as e:
        logger.warning(f"Falla en verificación de contraseña: {e}")
        return False


import time
def verify_session_validity(
    session: Session,
    user_id: int,
    token_version: int,
    last_activity_time: float,
    max_inactive_seconds: int = 1800,
) -> Tuple[bool, Optional[str]]:
    """
    Verifica que la sesión no haya caducado por inactividad y que la versión del token siga vigente.
    """
    if time.time() - last_activity_time > max_inactive_seconds:
        return False, "Sesión caducada por inactividad. Inicie sesión nuevamente."

    user = session.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        return False, "La cuenta de usuario no existe o se encuentra inactiva."

    if user.session_token_version != token_version:
        return False, "Su sesión ha sido revocada por actualización de perfil o seguridad."

    return True, None


def revoke_user_sessions(session: Session, user_id: int) -> None:
    """Invalida inmediatamente todas las sesiones activas de un usuario incrementando la versión del token."""
    user = session.query(User).filter(User.id == user_id).first()
    if user:
        user.session_token_version += 1
        session.flush()
        logger.info(f"Sesiones revocadas para usuario '{user.username}' (Versión: {user.session_token_version})")


def authenticate_user(
    session: Session,
    username_or_email: str,
    plain_password: str,
    ip_address: Optional[str] = None,
) -> Tuple[Optional[User], Optional[str]]:
    """
    Autentica a un usuario aplicando protección contra fuerza bruta y bloqueo progresivo.
    Retorna (User | None, error_message | None).
    """
    clean_identifier = username_or_email.strip().lower()
    user = (
        session.query(User)
        .filter((User.username == clean_identifier) | (User.email == clean_identifier))
        .first()
    )
    if not user:
        return None, "Credenciales inválidas."

    if not user.is_active:
        return None, "La cuenta de usuario se encuentra desactivada."

    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

    # 1. Verificar si la cuenta está bloqueada temporalmente
    if user.locked_until and user.locked_until > now:
        remaining = int((user.locked_until - now).total_seconds() / 60) + 1
        logger.warning(f"Intento de acceso a cuenta bloqueada: '{user.username}' (Restan ~{remaining} min)")
        return None, f"Cuenta bloqueada por múltiples intentos fallidos. Reintente en {remaining} minutos."

    # 2. Verificar contraseña
    if not verify_password(plain_password, user.hashed_password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
            user.locked_until = now + datetime.timedelta(minutes=ACCOUNT_LOCKOUT_MINUTES)
            logger.error(f"Cuenta '{user.username}' BLOQUEADA por {ACCOUNT_LOCKOUT_MINUTES} min tras {user.failed_login_attempts} intentos fallidos.")
            log_audit_event(session, "ACCOUNT_LOCKED", "User", user.id, user=user.username, ip_address=ip_address, new_data={"attempts": user.failed_login_attempts})
        else:
            log_audit_event(session, "LOGIN_FAILED", "User", user.id, user=user.username, ip_address=ip_address, new_data={"attempts": user.failed_login_attempts})

        session.flush()
        return None, "Credenciales inválidas."

    # 3. Acceso exitoso: resetear contadores de fallos y registrar login
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = now
    session.flush()

    logger.info(f"Usuario '{user.username}' autenticado exitosamente (Rol: {user.role}).")
    log_audit_event(session, "LOGIN_SUCCESS", "User", user.id, user=user.username, ip_address=ip_address)

    return user, None



def change_user_password(
    session: Session,
    user_id: int,
    new_password: str,
    old_password: Optional[str] = None,
    is_admin_override: bool = False,
    user_actor: Optional[str] = None,
) -> Tuple[bool, str]:
    """Cambia la contraseña de un usuario validando la fortaleza y credenciales previas."""
    user = session.query(User).filter(User.id == user_id).first()
    if not user:
        return False, "Usuario no encontrado."

    if not is_admin_override:
        if not old_password or not verify_password(old_password, user.hashed_password):
            return False, "La contraseña actual es incorrecta."

    is_strong, err = validate_password_strength(new_password)
    if not is_strong:
        return False, err or "Contraseña débil."

    user.hashed_password = hash_password(new_password)
    user.must_change_password = False
    user.password_changed_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    session.flush()

    log_audit_event(
        session,
        "CHANGE_PASSWORD",
        "User",
        user.id,
        user=user_actor or user.username,
        new_data={"must_change": False},
    )
    return True, "Contraseña actualizada exitosamente."


def create_user(
    session: Session,
    username: str,
    email: str,
    plain_password: str,
    full_name: str,
    role: str = "closer",
    must_change_password: bool = False,
    creator_user: Optional[User | str] = None,
) -> User:
    """Crea un nuevo usuario en la base de datos aplicando validación de permisos y fortaleza."""
    if role not in ROLE_PERMISSIONS:
        raise ValueError(f"Rol inválido: '{role}'. Roles válidos: {list(ROLE_PERMISSIONS.keys())}")

    # Evitar escalamiento: managers no pueden crear administradores
    if creator_user and isinstance(creator_user, User):
        if creator_user.role == "manager" and role == "admin":
            raise PermissionError("Un usuario con rol 'manager' no puede crear cuentas con rol 'admin'.")

    is_strong, err = validate_password_strength(plain_password)
    if not is_strong:
        raise ValueError(err or "Contraseña no cumple con los requisitos de seguridad.")

    user = User(
        username=username.strip().lower(),
        email=email.strip().lower(),
        hashed_password=hash_password(plain_password),
        full_name=full_name.strip(),
        role=role,
        is_active=True,
        must_change_password=must_change_password,
    )
    session.add(user)
    session.flush()
    logger.info(f"Usuario creado: {user.username} (Rol: {user.role})")
    log_audit_event(session, "CREATE_USER", "User", user.id, user=creator_user, new_data={"username": user.username, "role": role})
    return user


def setup_initial_admin(
    session: Session,
    username: str = "admin",
    email: str = "admin@consultora.com",
    full_name: str = "Administrador Corporativo",
    plain_password: Optional[str] = None,
) -> Tuple[User, str]:
    """
    Crea o reconfigura el superadministrador inicial con una contraseña de alta entropía.
    Retorna (User, generated_password).
    """
    generated_pwd = plain_password or secrets.token_urlsafe(16)
    existing_admin = session.query(User).filter(User.username == username.strip().lower()).first()

    if existing_admin:
        existing_admin.hashed_password = hash_password(generated_pwd)
        existing_admin.must_change_password = False
        existing_admin.failed_login_attempts = 0
        existing_admin.locked_until = None
        existing_admin.is_active = True
        session.flush()
        logger.warning(f"Superadministrador '{username}' restablecido con nueva contraseña.")
        log_audit_event(session, "ADMIN_BOOTSTRAP_RESET", "User", existing_admin.id, user="bootstrap_cli")
        return existing_admin, generated_pwd

    admin_user = User(
        username=username.strip().lower(),
        email=email.strip().lower(),
        hashed_password=hash_password(generated_pwd),
        full_name=full_name.strip(),
        role="admin",
        is_active=True,
        must_change_password=False,
    )
    session.add(admin_user)
    session.flush()
    logger.info(f"Superadministrador '{username}' inicializado exitosamente.")
    log_audit_event(session, "ADMIN_BOOTSTRAP_CREATE", "User", admin_user.id, user="bootstrap_cli")
    return admin_user, generated_pwd


def has_permission(user: Optional[User | Dict[str, Any]], permission: str) -> bool:
    """Comprueba si un usuario tiene un permiso específico."""
    if not user:
        return False
    if isinstance(user, dict):
        role = user.get("role", "")
        is_active = user.get("is_active", True)
    else:
        role = user.role
        is_active = user.is_active

    if not is_active:
        return False
    return permission in ROLE_PERMISSIONS.get(role, [])


def seed_default_users_if_needed(database_url: Optional[str] = None, force: bool = False) -> None:
    """
    Inicializa la BD. El sembrado automático está DESHABILITADO por defecto en producción
    y solo se ejecuta si está expresamente habilitado en configuración de desarrollo o forzado.
    """
    init_db(database_url)
    cfg = get_config()
    
    # Bloqueo total de sembrado automático en producción salvo que sea invocado explícitamente con force=True
    if not (force or cfg.auto_seed_default_users):
        return

    with get_db_session(database_url) as session:
        count = session.query(User).count()
        if count == 0:
            logger.warning("Inicializando usuarios de prueba...")
            setup_initial_admin(session, "admin", "admin@consultora.com", "Administrador Corporativo", "Admin#Secure2026!")
            create_user(session, "jony", "jony@consultora.com", "Jony#Secure2026!", "Jony (Closer Senior)", "closer")
            create_user(session, "luisa", "luisa@consultora.com", "Luisa#Secure2026!", "Luisa (Closer Comercial)", "closer")
            create_user(session, "sergio", "sergio@consultora.com", "Sergio#Secure2026!", "Sergio (Closer Agro)", "closer")
            create_user(session, "viewer", "viewer@consultora.com", "Viewer#Secure2026!", "Auditor de Reportes", "viewer")
            logger.warning("Usuarios de prueba creados.")

