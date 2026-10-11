"""
Pruebas unitarias para el administrador de backups cifrados y recuperación (finance_app/backup_manager.py).
"""

from pathlib import Path
from finance_app.backup_manager import (
    create_backup,
    list_backups,
    restore_backup,
    backup_whatsapp_session,
    compute_file_sha256,
)


def test_create_and_list_backups(tmp_path):
    source_file = tmp_path / "test_data.xlsx"
    source_file.write_text("dummy excel data")
    backup_dir = tmp_path / "backups"

    # Crear backup cifrado
    backup_path = create_backup(source_file, tag="unit_test", backup_dir=backup_dir, encrypt=True)
    assert backup_path is not None
    assert backup_path.exists()
    assert backup_path.name.endswith(".enc")

    # Verificar que se generó el checksum SHA-256
    chk_file = backup_path.with_suffix(backup_path.suffix + ".sha256")
    assert chk_file.exists()

    # Listar backups
    backups = list_backups(backup_dir=backup_dir)
    assert len(backups) == 1
    assert backups[0]["filename"] == backup_path.name
    assert backups[0]["encrypted"] is True
    assert backups[0]["has_checksum"] is True


def test_restore_encrypted_backup(tmp_path):
    source_file = tmp_path / "original.xlsx"
    source_file.write_text("version 1 - sensitive data")
    backup_dir = tmp_path / "backups"

    # Crear backup cifrado
    backup_path = create_backup(source_file, tag="v1", backup_dir=backup_dir, encrypt=True)
    
    # Mutar archivo original
    source_file.write_text("version 2 corrupted")
    assert source_file.read_text() == "version 2 corrupted"

    # Restaurar
    success = restore_backup(backup_path, source_file, create_safety_backup=False)
    assert success is True
    assert source_file.read_text() == "version 1 - sensitive data"


def test_restore_tamper_detection(tmp_path):
    source_file = tmp_path / "tamper_test.xlsx"
    source_file.write_text("authentic data")
    backup_dir = tmp_path / "backups"

    backup_path = create_backup(source_file, tag="tamper", backup_dir=backup_dir, encrypt=True)
    
    # Manipular el archivo de backup
    with open(backup_path, "ab") as f:
        f.write(b"MALICIOUS_BYTES_INJECTED")

    # La restauración debe fallar por checksum SHA-256 mismatch
    restored_dest = tmp_path / "restored.xlsx"
    restored_dest.write_text("known-good destination")
    success = restore_backup(backup_path, restored_dest, create_safety_backup=False)
    assert success is False
    assert restored_dest.read_text() == "known-good destination"


def test_backup_rotation_limit(tmp_path):
    source_file = tmp_path / "rotating_data.xlsx"
    source_file.write_text("content")
    backup_dir = tmp_path / "backups"

    # Crear 4 backups con límite max_backups=2
    for i in range(4):
        create_backup(source_file, tag=f"batch_{i}", backup_dir=backup_dir, max_backups=2, encrypt=True)

    backups = list_backups(backup_dir=backup_dir)
    assert len(backups) <= 2


def test_backup_whatsapp_session(tmp_path):
    session_dir = tmp_path / "auth_info_baileys"
    session_dir.mkdir()
    (session_dir / "creds.json").write_text('{"token": "xyz"}')
    backup_dir = tmp_path / "backups"

    # Modo cifrado por defecto
    zip_path = backup_whatsapp_session(session_dir=session_dir, backup_dir=backup_dir, encrypt=True)
    assert zip_path is not None
    assert zip_path.exists()
    assert zip_path.name.endswith(".zip.enc")

    chk_file = zip_path.with_suffix(zip_path.suffix + ".sha256")
    assert chk_file.exists()


def test_backup_restore_roundtrip_full_integrity(tmp_path):
    """
    Prueba exhaustiva de ciclo completo: creación, cifrado AES, mutación,
    detección de corrupción y restauración fiel de base de datos SQLite.
    """
    db_file = tmp_path / "production_vault.db"
    db_file.write_bytes(b"SQLITE_DATABASE_ENCRYPTED_HEADER_TEST_BYTES_" + b"0" * 512)
    backup_dir = tmp_path / "secure_backups"

    # 1. Crear backup cifrado
    enc_backup = create_backup(db_file, tag="prod_v1", backup_dir=backup_dir, encrypt=True)
    assert enc_backup.exists()
    assert enc_backup.read_bytes() != db_file.read_bytes()  # El contenido en disco está cifrado

    # 2. Reemplazar archivo destino con datos corruptos
    db_file.write_bytes(b"CORRUPTED_DATABASE_DATA")
    assert db_file.read_bytes() == b"CORRUPTED_DATABASE_DATA"

    # 3. Restaurar y verificar integridad total
    restore_success = restore_backup(enc_backup, db_file, create_safety_backup=True)
    assert restore_success is True
    assert db_file.read_bytes() == b"SQLITE_DATABASE_ENCRYPTED_HEADER_TEST_BYTES_" + b"0" * 512

