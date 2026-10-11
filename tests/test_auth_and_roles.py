"""
Pruebas unitarias para autenticación, hashing bcrypt, bloqueo por fuerza bruta y roles RBAC (finance_app/db/auth_service.py).
"""

from finance_app.db.session import get_db_session, reset_db
from finance_app.db.auth_service import (
    hash_password,
    verify_password,
    create_user,
    authenticate_user,
    has_permission,
    seed_default_users_if_needed,
    validate_password_strength,
)
from finance_app.db.models import User


def test_password_hashing_and_verification():
    pwd = "SuperSecretPassword123!"
    hashed = hash_password(pwd)
    assert hashed != pwd
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
    assert verify_password(pwd, hashed) is True
    assert verify_password("wrongPassword", hashed) is False


def test_password_strength_validator():
    is_valid, _ = validate_password_strength("weak")
    assert is_valid is False

    is_valid, _ = validate_password_strength("alllowercaseletters")
    assert is_valid is False

    is_valid, _ = validate_password_strength("Valid#Password2026")
    assert is_valid is True


def test_user_creation_and_authentication():
    db_url = "sqlite://"
    reset_db(db_url)
    strong_pwd = "SecurePassword#2026"

    with get_db_session(db_url) as session:
        user = create_user(session, "jony_closer", "jony@test.com", strong_pwd, "Jony Closer", role="closer")
        assert user.id is not None
        assert user.role == "closer"

        # Autenticación correcta
        auth_user, err = authenticate_user(session, "jony_closer", strong_pwd)
        assert auth_user is not None
        assert err is None
        assert auth_user.id == user.id

        # Autenticación por email
        auth_by_email, err_email = authenticate_user(session, "jony@test.com", strong_pwd)
        assert auth_by_email is not None
        assert err_email is None

        # Autenticación fallida
        failed_user, err_failed = authenticate_user(session, "jony_closer", "bad_password")
        assert failed_user is None
        assert err_failed is not None

        unknown_user, err_unk = authenticate_user(session, "unknown_user", strong_pwd)
        assert unknown_user is None
        assert err_unk is not None


def test_brute_force_lockout():
    db_url = "sqlite://"
    reset_db(db_url)
    strong_pwd = "SecurePassword#2026"

    with get_db_session(db_url) as session:
        user = create_user(session, "target_user", "target@test.com", strong_pwd, "Target User", role="closer")
        # 5 Intentos fallidos provocan bloqueo temporal
        for _ in range(5):
            authenticate_user(session, "target_user", "wrong_pwd")

        # Quinto intento bloquea la cuenta
        session.refresh(user)
        assert user.is_locked is True

        # Intento de login incluso con password correcto falla por estar bloqueada
        locked_u, err_locked = authenticate_user(session, "target_user", strong_pwd)
        assert locked_u is None
        assert "bloqueada" in err_locked.lower()




def test_rbac_permissions():
    admin = User(username="adm", role="admin", is_active=True)
    closer = User(username="cls", role="closer", is_active=True)
    viewer = User(username="viw", role="viewer", is_active=True)
    inactive = User(username="inact", role="admin", is_active=False)

    assert has_permission(admin, "manage_users") is True
    assert has_permission(admin, "view_all") is True
    assert has_permission(closer, "manage_users") is False
    assert has_permission(closer, "create_customer") is True
    assert has_permission(viewer, "view_all") is True
    assert has_permission(viewer, "create_customer") is False
    assert has_permission(inactive, "view_all") is False


def test_seed_default_users():
    db_url = "sqlite://"
    reset_db(db_url)
    seed_default_users_if_needed(db_url, force=True)

    with get_db_session(db_url) as session:
        users = session.query(User).all()
        usernames = [u.username for u in users]
        assert "admin" in usernames
        assert "jony" in usernames
        assert "luisa" in usernames
        assert "sergio" in usernames
