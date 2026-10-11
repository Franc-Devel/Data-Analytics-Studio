"""
Pruebas Unitarias para el Módulo de Autenticación Cloud Airtable y 2FA (Google Authenticator).
"""

from unittest.mock import patch, MagicMock
import pyotp
import pytest

from finance_app.services.airtable_auth_service import (
    hash_password,
    check_password,
    generate_totp_secret,
    get_totp_uri,
    generate_qr_code_image_bytes,
    verify_totp_code,
    authenticate_user_with_airtable,
    reset_password_via_2fa,
    activate_user_2fa,
    validate_password_policy,
    check_login_rate_limit,
    record_failed_login,
    clear_failed_logins,
    create_encrypted_client_session_token,
    verify_encrypted_client_session_token,
    create_airtable_user,
    delete_airtable_user,
    admin_reset_user_password,
    admin_update_user_account,
    is_valid_email,
)


def test_hash_and_check_password():
    raw_pwd = "SuperSecretPassword2026!"
    hashed = hash_password(raw_pwd)
    assert hashed != raw_pwd
    assert check_password(raw_pwd, hashed) is True
    assert check_password("WrongPassword123", hashed) is False


def test_totp_generation_and_verification():
    secret = generate_totp_secret()
    assert len(secret) == 32
    
    uri = get_totp_uri(secret, "admin@consultora.com")
    assert "otpauth://totp/" in uri
    assert "Consultora" in uri

    qr_bytes = generate_qr_code_image_bytes(uri)
    assert isinstance(qr_bytes, bytes)
    assert len(qr_bytes) > 200

    # Generar código con pyotp y validar
    current_code = pyotp.TOTP(secret).now()
    assert verify_totp_code(secret, current_code) is True
    assert verify_totp_code(secret, "000000") is False


def test_authenticate_user_with_reset_generico():
    mock_user = {
        "record_id": "recTest123",
        "email": "closer@consultora.com",
        "nombre": "Closer Juan",
        "rol": "closer",
        "password_hash": hash_password("OldPassword123"),
        "totp_secret_encrypted": "aesgcm:fake",
        "totp_enabled": True,
        "reset_generico": True,
        "activo": True,
    }

    with patch("finance_app.services.airtable_auth_service.find_user_by_email", return_value=mock_user):
        # Con contraseña genérica correcta
        ok, status, user = authenticate_user_with_airtable("closer@consultora.com", "Consultora2026!")
        assert ok is True
        assert status == "RESET_GENERICO_ACTIVO"

        # Con contraseña incorrecta
        ok, status, user = authenticate_user_with_airtable("closer@consultora.com", "WrongPassword")
        assert ok is False


def test_authenticate_user_with_2fa_success():
    secret = generate_totp_secret()
    # Usamos mock para decrypt_field
    raw_pwd = "UserSecret123!"
    mock_user = {
        "record_id": "recTest456",
        "email": "luisa@consultora.com",
        "nombre": "Luisa Vendedora",
        "rol": "closer",
        "password_hash": hash_password(raw_pwd),
        "totp_secret_encrypted": "encrypted_token",
        "totp_enabled": True,
        "reset_generico": False,
        "activo": True,
    }

    valid_code = pyotp.TOTP(secret).now()

    with patch("finance_app.services.airtable_auth_service.find_user_by_email", return_value=mock_user):
        with patch("finance_app.services.airtable_auth_service.decrypt_field", return_value=secret):
            # 1. Sin código TOTP debe solicitarlo
            ok, status, user = authenticate_user_with_airtable("luisa@consultora.com", raw_pwd, totp_code=None)
            assert ok is False
            assert status == "REQUIERE_2FA_CODE"

            # 2. Con código TOTP válido
            ok, status, user = authenticate_user_with_airtable("luisa@consultora.com", raw_pwd, totp_code=valid_code)
            assert ok is True
            assert status == "AUTENTICADO"
            assert user["email"] == "luisa@consultora.com"


def test_authenticate_inactive_user():
    mock_user = {
        "record_id": "recInactive",
        "email": "banned@consultora.com",
        "nombre": "Inactivo",
        "rol": "viewer",
        "password_hash": hash_password("pass123"),
        "totp_enabled": True,
        "reset_generico": False,
        "activo": False,
    }
    with patch("finance_app.services.airtable_auth_service.find_user_by_email", return_value=mock_user):
        ok, status, user = authenticate_user_with_airtable("banned@consultora.com", "pass123")
        assert ok is False
        assert "inactiva o suspendida" in status


def test_password_policy():
    # Muy corta (< 6 caracteres)
    ok, err = validate_password_policy("Ab1!")
    assert ok is False
    assert "entre 6 y 20 caracteres" in err

    # Muy larga (> 20 caracteres)
    ok, err = validate_password_policy("Ab1!SuperLargaContrasenaQueSuperaVeinteCaracteres")
    assert ok is False
    assert "entre 6 y 20 caracteres" in err

    # Sin minúscula
    ok, err = validate_password_policy("ABCDEF1!")
    assert ok is False
    assert "letra minúscula" in err

    # Sin mayúscula
    ok, err = validate_password_policy("abcdef1!")
    assert ok is False
    assert "letra mayúscula" in err

    # Sin número
    ok, err = validate_password_policy("Abcdefgh!")
    assert ok is False
    assert "número" in err

    # Sin caracter especial
    ok, err = validate_password_policy("Abcdefgh1")
    assert ok is False
    assert "caracter especial" in err

    # Cumple todos los requisitos
    ok, err = validate_password_policy("Valida#2026")
    assert ok is True
    assert err == ""


def test_login_rate_limiting():
    test_id = "attacker@test.com"
    clear_failed_logins(test_id)

    # Inicialmente permitido
    allowed, rem = check_login_rate_limit(test_id, max_attempts=3, window_seconds=60, lockout_duration=100)
    assert allowed is True
    assert rem == 0

    # Registrar 3 intentos fallidos
    record_failed_login(test_id)
    record_failed_login(test_id)
    record_failed_login(test_id)

    # Ahora debe estar bloqueado
    allowed, rem = check_login_rate_limit(test_id, max_attempts=3, window_seconds=60, lockout_duration=100)
    assert allowed is False
    assert rem > 0

    # Limpiar y verificar que se desbloquea
    clear_failed_logins(test_id)
    allowed, rem = check_login_rate_limit(test_id, max_attempts=3, window_seconds=60, lockout_duration=100)
    assert allowed is True
    assert rem == 0


def test_encrypted_client_session_token_roundtrip():
    user = {
        "id": "recTestClient1",
        "email": "seguro@consultora.com",
        "nombre": "Agente Seguro",
        "rol": "admin",
    }

    # Generar token cifrado militar con AES-256-GCM
    token = create_encrypted_client_session_token(user, max_age_seconds=3600)
    assert token.startswith("aesgcm:")
    # Verificar que datos sensibles no están en texto plano
    assert "seguro@consultora.com" not in token
    assert "recTestClient1" not in token

    # Descifrar y validar contenido
    session_data = verify_encrypted_client_session_token(token)
    assert session_data is not None
    assert session_data["id"] == "recTestClient1"
    assert session_data["email"] == "seguro@consultora.com"
    assert session_data["role"] == "admin"
    assert session_data["session_source"] == "encrypted_vault"

    # Manipular token (ataque de tampering) debe fallar (retornar None)
    tampered_token = token[:-4] + "AAAA"
    assert verify_encrypted_client_session_token(tampered_token) is None

    # Token expirado debe fallar
    expired_token = create_encrypted_client_session_token(user, max_age_seconds=-10)
    assert verify_encrypted_client_session_token(expired_token) is None


def test_admin_cannot_be_deleted():
    admin_user = {
        "record_id": "recAdmin1",
        "email": "master@consultora.com",
        "nombre": "Admin Master",
        "rol": "admin",
    }
    closer_user = {
        "record_id": "recCloser2",
        "email": "vendedor@consultora.com",
        "nombre": "Vendedor",
        "rol": "closer",
    }
    current_admin = {
        "id": "recAdmin1",
        "email": "master@consultora.com",
        "username": "master@consultora.com",
        "role": "admin",
    }

    # 1. Intentar eliminar a un usuario con rol 'admin' debe ser bloqueado por ciberseguridad
    ok, msg = delete_airtable_user("recAdmin1", admin_user, current_admin)
    assert ok is False
    assert "protegidas contra eliminación" in msg

    # 2. Intentar eliminarse a sí mismo debe ser bloqueado
    ok, msg = delete_airtable_user("recAdmin1", {"email": "master@consultora.com", "rol": "viewer"}, current_admin)
    assert ok is False
    assert "tu propia cuenta" in msg

    # 3. Eliminar un usuario no-admin (closer) debe permitirse
    with patch("requests.delete") as mock_delete:
        mock_delete.return_value.status_code = 200
        ok, msg = delete_airtable_user("recCloser2", closer_user, current_admin)
        assert ok is True
        assert "eliminada permanentemente" in msg


def test_admin_reset_user_password():
    with patch("finance_app.services.airtable_auth_service.update_airtable_user", return_value=True) as mock_update:
        ok, msg = admin_reset_user_password("recUser99", "olvidadizo@consultora.com", generic_password="Consultora2026!")
        assert ok is True
        assert "reestablecida" in msg
        mock_update.assert_called_once()
        call_args = mock_update.call_args[0]
        assert call_args[0] == "recUser99"
        assert call_args[1]["reset_generico"] is True
        assert "password_hash" in call_args[1]


def test_admin_update_user_account_self_protection():
    current_admin = {
        "id": "recAdmin1",
        "email": "master@consultora.com",
        "username": "master@consultora.com",
        "role": "admin",
    }

    # Intentar revocar su propio rol de admin
    ok, msg = admin_update_user_account(
        record_id="recAdmin1",
        fields={"rol": "closer"},
        target_user={"email": "master@consultora.com", "rol": "admin"},
        current_admin=current_admin,
    )
    assert ok is False
    assert "No puedes revocar tu propio rol" in msg

    # Intentar suspender su propia cuenta
    ok, msg = admin_update_user_account(
        record_id="recAdmin1",
        fields={"activo": False},
        target_user={"email": "master@consultora.com", "rol": "admin"},
        current_admin=current_admin,
    )
    assert ok is False
    assert "No puedes suspender tu propia cuenta" in msg


def test_single_admin_enforcement_on_registration():
    # Caso 1: Si no hay admins, el primer usuario se convierte en admin
    with patch("finance_app.services.airtable_auth_service.fetch_all_users", return_value=[]):
        with patch("finance_app.services.airtable_auth_service.find_user_by_email", return_value=None):
            with patch("requests.post") as mock_post:
                mock_post.return_value.status_code = 201
                mock_post.return_value.json.return_value = {"id": "recFirstUser"}
                ok, msg, user = create_airtable_user("dueno@consultora.com", "Dueño", "Valida#2026", rol="closer")
                assert ok is True
                assert user["rol"] == "admin"

    # Caso 2: Si ya existe un admin, nadie más puede registrarse como admin
    existing_admin = [{"record_id": "recAdmin1", "email": "dueno@consultora.com", "rol": "admin"}]
    with patch("finance_app.services.airtable_auth_service.fetch_all_users", return_value=existing_admin):
        with patch("finance_app.services.airtable_auth_service.find_user_by_email", return_value=None):
            ok, msg, user = create_airtable_user("intruso@consultora.com", "Intruso", "Valida#2026", rol="admin")
            assert ok is False
            assert "administrador único" in msg.lower()


def test_single_admin_enforcement_on_update():
    existing_admin = [{"record_id": "recAdmin1", "email": "dueno@consultora.com", "rol": "admin"}]
    current_admin = {
        "id": "recAdmin1",
        "email": "dueno@consultora.com",
        "username": "dueno@consultora.com",
        "role": "admin",
    }
    target_closer = {
        "record_id": "recCloser2",
        "email": "empleado@consultora.com",
        "rol": "closer",
    }

    # Intentar elevar el rol de un closer a admin cuando ya existe un admin registrado debe denegarse
    with patch("finance_app.services.airtable_auth_service.fetch_all_users", return_value=existing_admin):
        ok, msg = admin_update_user_account(
            record_id="recCloser2",
            fields={"rol": "admin"},
            target_user=target_closer,
            current_admin=current_admin,
        )
        assert ok is False
        assert "Solamente se permite un (1) Administrador único" in msg


def test_is_valid_email():
    # Emails válidos
    assert is_valid_email("usuario@empresa.com") is True
    assert is_valid_email("admin.consultora@sub.dominio.com.ar") is True
    assert is_valid_email("test+tag@gmail.com") is True
    assert is_valid_email("a_b-c@domain.co") is True
    assert is_valid_email("  usuario@empresa.com  ") is True  # con strip() interno

    # Emails inválidos
    assert is_valid_email("") is False
    assert is_valid_email(None) is False
    assert is_valid_email("pepe@") is False
    assert is_valid_email("@dominio.com") is False
    assert is_valid_email("pepe@dominio") is False
    assert is_valid_email("pepe@dominio.c") is False  # TLD < 2 caracteres
    assert is_valid_email("pepe @dominio.com") is False
    assert is_valid_email("pepe@ dominio.com") is False
    assert is_valid_email("pepe@@dominio.com") is False
    assert is_valid_email("pepe..algo@dominio.com") is False
    assert is_valid_email("pepe@dominio..com") is False


def test_create_airtable_user_rejects_invalid_email():
    ok, msg, user = create_airtable_user("pepe@", "Pepe", "Valid#Pass2026", rol="closer")
    assert ok is False
    assert "formato válido" in msg
    assert user is None


def test_authenticate_user_rejects_invalid_email():
    ok, status, user = authenticate_user_with_airtable("pepe@", "Valid#Pass2026")
    assert ok is False
    assert "formato válido" in status
    assert user is None


def test_reset_password_via_2fa_rejects_invalid_email():
    ok, msg = reset_password_via_2fa("pepe@", "123456", "Valid#Pass2026")
    assert ok is False
    assert "formato válido" in msg


def test_validate_registration_fields_matching_login_jsx():
    from finance_app.services.airtable_auth_service import validate_registration_fields

    # Nombre < 3 caracteres
    err = validate_registration_fields("ab", "user@correo.com", "Secret123!", "Secret123!")
    assert err == "El nombre debe contener al menos 3 caracteres."

    # Email inválido
    err = validate_registration_fields("Juan Perez", "invalido", "Secret123!", "Secret123!")
    assert err == "Ingresa un correo electrónico con formato válido."

    # Contraseña corta
    err = validate_registration_fields("Juan Perez", "user@correo.com", "Ab1!", "Ab1!")
    assert err == "La contraseña debe tener entre 6 y 20 caracteres."

    # Contraseñas no coinciden
    err = validate_registration_fields("Juan Perez", "user@correo.com", "Secret123!", "Different123!")
    assert err == "Las contraseñas no coinciden."

    # Todo válido
    err = validate_registration_fields("Juan Perez", "user@correo.com", "Secret123!", "Secret123!")
    assert err is None




