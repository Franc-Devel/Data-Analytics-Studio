"""
Nexo Analytics - Suite de Pruebas de Seguridad Integral
Valida:
1. Anti-IDOR y Aislamiento por Rol (Closer vs Manager vs Viewer)
2. Auditoría Inmutable con Hash Chaining SHA-256 y Detección de Manipulación
3. Cifrado a Nivel de Campo (FLE) y Blind Index
4. Seguridad en Carga de Archivos y Sanitización de Inyección de Fórmulas
5. Privacidad y Cumplimiento Normativo Ley 25.326 (SAR y Derecho al Olvido)
"""

import pytest
import pandas as pd
from finance_app.db.session import get_db_session, reset_db
from finance_app.db.models import User, Customer, Opportunity, Task, AuditLog
from finance_app.db.auth_service import create_user
from finance_app.db.crm_service import (
    create_or_update_customer,
    get_customer_by_id,
    search_customers,
    create_opportunity,
    update_opportunity_stage,
    create_task,
    complete_task,
    anonymize_customer,
    export_customer_dossier,
)
from finance_app.db.audit_service import log_audit_event, verify_audit_integrity
from finance_app.db.crypto import encrypt_field, decrypt_field, compute_blind_index
from finance_app.services.file_security import (
    validate_uploaded_file,
    sanitize_formula_value,
    sanitize_dataframe_formulas,
)


def test_anti_idor_and_role_isolation():
    db_url = "sqlite://"
    reset_db(db_url)

    with get_db_session(db_url) as session:
        # Crear usuarios con contraseñas seguras
        closer1 = create_user(session, "closer_1", "c1@test.com", "Secure#Pass1234!", "Closer Uno", "closer")
        closer2 = create_user(session, "closer_2", "c2@test.com", "Secure#Pass1234!", "Closer Dos", "closer")
        viewer = create_user(session, "viewer_user", "v@test.com", "Secure#Pass1234!", "Viewer User", "viewer")
        manager = create_user(session, "manager_user", "m@test.com", "Secure#Pass1234!", "Manager User", "manager")

        # 1. Closer 1 crea su cliente
        cust1, _ = create_or_update_customer(
            session, "+549111111", "Cliente de Closer 1", assigned_user_id=closer1.id, user_actor=closer1
        )

        # 2. Closer 2 intenta acceder por ID directo a cliente de Closer 1 -> Debe lanzar PermissionError (Anti-IDOR)
        with pytest.raises(PermissionError, match="Acceso denegado"):
            get_customer_by_id(session, cust1.id, user_actor=closer2)

        # 3. Manager sí puede acceder al cliente de Closer 1
        cust_m = get_customer_by_id(session, cust1.id, user_actor=manager)
        assert cust_m is not None
        assert cust_m.id == cust1.id

        # 4. En búsquedas, Closer 2 no ve al cliente asignado a Closer 1
        results_c2 = search_customers(session, user_actor=closer2)
        assert cust1.id not in [c.id for c in results_c2]

        # 5. Viewer intenta crear un cliente -> Debe lanzar PermissionError
        with pytest.raises(PermissionError, match="viewer"):
            create_or_update_customer(session, "+549222222", "Cliente Ilegal", user_actor=viewer)


def test_immutable_audit_hash_chaining_and_tampering():
    db_url = "sqlite://"
    reset_db(db_url)

    with get_db_session(db_url) as session:
        # Registrar varios eventos
        log_audit_event(session, "LOGIN_SUCCESS", "User", 1, user="admin")
        log_audit_event(session, "CREATE", "Customer", 101, user="closer_1", new_data={"phone": "+5491133334444"})
        log_audit_event(session, "UPDATE", "Opportunity", 202, user="closer_1", old_data={"stage": "PROSPECCION"}, new_data={"stage": "NEGOCIACION"})

        # Verificar integridad inicial
        is_valid, count, msg = verify_audit_integrity(session)
        assert is_valid is True
        assert count == 3
        assert "verificada íntegra" in msg

        # Simular ataque de manipulación directa en BD sobre el registro intermedio
        entry2 = session.query(AuditLog).filter(AuditLog.id == 2).first()
        entry2.new_data_json = '{"phone": "+549999999999"}'
        session.flush()

        # El verificador debe detectar la alteración
        is_valid_tampered, failed_idx, err_msg = verify_audit_integrity(session)
        assert is_valid_tampered is False
        assert "Manipulación de datos detectada" in err_msg


def test_field_level_encryption_and_blind_index():
    plaintext = "Notas confidenciales de negociación financiera: DNI 35.123.456"
    encrypted = encrypt_field(plaintext)
    assert encrypted != plaintext
    assert encrypted.startswith("aesgcm:")

    decrypted = decrypt_field(encrypted)
    assert decrypted == plaintext

    # Blind Index
    phone1 = "+54 9 11 2345-6789"
    phone2 = "5491123456789"
    idx1 = compute_blind_index(phone1, is_phone=True)
    idx2 = compute_blind_index(phone2, is_phone=True)
    assert idx1 == idx2
    assert len(idx1) == 64


def test_file_upload_security_and_formula_sanitization():
    # 1. Archivo vacío
    is_valid, err = validate_uploaded_file(b"", "empty.xlsx")
    assert is_valid is False

    # 2. Extensión peligrosa
    is_valid, err = validate_uploaded_file(b"PK\x03\x04dummy", "macro.xlsm")
    assert is_valid is False
    assert "peligroso" in err or "Formato no permitido" in err

    # 3. CSV con bytes nulos
    is_valid, err = validate_uploaded_file(b"col1,col2\nval1,\x00malicious", "data.csv")
    assert is_valid is False
    assert "binarios" in err

    # 4. Inyección de fórmulas CSV/Excel
    malicious_formula = "=cmd|'/c calc'!A0"
    sanitized = sanitize_formula_value(malicious_formula)
    assert sanitized == "'=cmd|'/c calc'!A0"

    # 5. DataFrame sanitization
    df = pd.DataFrame({
        "nombre": ["Juan", "=SUM(A1:A10)", "@HYPERLINK('http://evil.com')"],
        "monto": [100, 200, 300],
    })
    clean_df = sanitize_dataframe_formulas(df)
    assert clean_df["nombre"].iloc[1] == "'=SUM(A1:A10)"
    assert clean_df["nombre"].iloc[2] == "'@HYPERLINK('http://evil.com')"
    assert clean_df["monto"].iloc[0] == 100


def test_argentine_law_25326_sar_and_anonymization():
    db_url = "sqlite://"
    reset_db(db_url)

    with get_db_session(db_url) as session:
        admin = create_user(session, "admin_legal", "legal@test.com", "Secure#Pass1234!", "Admin Legal", "admin")
        cust, _ = create_or_update_customer(
            session,
            "+5491144445555",
            "Juan Perez Titular",
            email="juan.perez@empresa.com",
            company="Perez Agro",
            notes="Cliente VIP",
            user_actor=admin,
        )

        # 1. Exportación de expediente (SAR)
        dossier = export_customer_dossier(session, cust.id, user_actor=admin)
        assert dossier["titular"]["nombre"] == "Juan Perez Titular"
        assert dossier["titular"]["telefono"] == "+5491144445555"

        # 2. Derecho al Olvido (Anonimización irreversible)
        success = anonymize_customer(session, cust.id, user_actor=admin)
        assert success is True

        # Verificar que la PII fue reemplazada
        session.refresh(cust)
        assert "Titular Suprimido" in cust.full_name
        assert cust.email.endswith("@deleted.internal")
        assert cust.notes == "[DATOS PERSONALES SUPRIMIDOS CONFORME A LEY 25.326]"
