"""
Nexo Analytics - Script de Migración y Cifrado Retroactivo de Datos Existentes
Recorre todas las tablas de clientes, usuarios y actividades, cifra campos sensibles en texto plano
con AES-256-GCM y regenera todos los Blind Indexes (HMAC-SHA256).

Uso:
  python scripts/migrate_and_encrypt_existing_data.py --dry-run
  python scripts/migrate_and_encrypt_existing_data.py --execute
"""

import sys
from pathlib import Path

# Añadir raíz al sys.path
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

from sqlalchemy.orm.attributes import flag_modified
from finance_app.db.session import get_db_session, init_db
from finance_app.db.models import Customer, CustomerSearchToken, User, ActivityLog
from finance_app.db.crypto import (
    compute_blind_index,
    compute_name_token_hashes,
    compute_name_tokens_index,
    compute_phone_token_hashes,
    compute_phone_tokens_index,
)
from finance_app.logging_config import get_logger

logger = get_logger("data_migration")


def migrate_data(dry_run: bool = True) -> None:
    print("=" * 70)
    print(" [*] MIGRACION Y CIFRADO RETROACTIVO DE DATOS (AES-256-GCM + BLIND INDEX)")
    print("=" * 70)
    print(f"Modo: {'SIMULACION (DRY-RUN)' if dry_run else 'EJECUCION REAL (COMMIT)'}\n")

    init_db()

    with get_db_session() as session:
        # 1. Migrar y reescribir cifrado en Clientes
        customers = session.query(Customer).all()
        print(f"Examinando {len(customers)} registros en tabla 'customers'...")
        migrated_customers = 0

        for cust in customers:
            # Reasignación explícita para activar TypeDecorator (EncryptedString / EncryptedText)
            if cust.phone:
                raw_phone = str(cust.phone)
                cust.phone = raw_phone
                cust.phone_blind_index = compute_blind_index(raw_phone, is_phone=True)
                cust.phone_tokens_index = compute_phone_tokens_index(raw_phone)
                flag_modified(cust, "phone")
                flag_modified(cust, "phone_blind_index")
                flag_modified(cust, "phone_tokens_index")

            if cust.full_name:
                raw_name = str(cust.full_name)
                cust.full_name = raw_name
                cust.name_blind_index = compute_blind_index(raw_name, is_phone=False)
                cust.name_tokens_index = compute_name_tokens_index(raw_name, cust.company)
                flag_modified(cust, "full_name")
                if cust.name_blind_index:
                    flag_modified(cust, "name_blind_index")
                if cust.name_tokens_index:
                    flag_modified(cust, "name_tokens_index")

            if cust.email:
                cust.email = str(cust.email)
                flag_modified(cust, "email")

            if cust.company:
                cust.company = str(cust.company)
                flag_modified(cust, "company")

            if cust.document_id:
                cust.document_id = str(cust.document_id)
                flag_modified(cust, "document_id")

            if cust.notes:
                cust.notes = str(cust.notes)
                flag_modified(cust, "notes")

            session.query(CustomerSearchToken).filter(
                CustomerSearchToken.customer_id == cust.id
            ).delete(synchronize_session=False)
            session.add_all([
                CustomerSearchToken(customer_id=cust.id, token_type=token_type, token_hash=token_hash)
                for token_type, tokens in (
                    ("name", compute_name_token_hashes(cust.full_name, cust.company)),
                    ("phone", compute_phone_token_hashes(cust.phone)),
                )
                for token_hash in tokens
            ])

            migrated_customers += 1

        print(f"[OK] Clientes procesados y re-cifrados: {migrated_customers}")

        # 2. Migrar y reescribir cifrado en Usuarios
        users = session.query(User).all()
        print(f"\nExaminando {len(users)} registros en tabla 'users'...")
        migrated_users = 0

        for u in users:
            if u.mfa_secret:
                u.mfa_secret = str(u.mfa_secret)
                flag_modified(u, "mfa_secret")
                migrated_users += 1
            if u.mfa_recovery_codes_hash:
                u.mfa_recovery_codes_hash = str(u.mfa_recovery_codes_hash)
                flag_modified(u, "mfa_recovery_codes_hash")

        print(f"[OK] Usuarios procesados y re-cifrados: {migrated_users}")

        # 3. Migrar y reescribir cifrado en ActivityLogs
        activities = session.query(ActivityLog).all()
        print(f"\nExaminando {len(activities)} registros en tabla 'activity_logs'...")
        migrated_activities = 0
        for act in activities:
            if act.content:
                act.content = str(act.content)
                flag_modified(act, "content")
                migrated_activities += 1
        print(f"[OK] Actividades procesadas y re-cifradas: {migrated_activities}")

        if dry_run:
            print("\n[DRY-RUN] Cambios no persistidos. Ejecute con --execute para aplicar.")
            session.rollback()
        else:
            session.flush()
            session.commit()
            print("\n[OK] Migracion aplicada y confirmada exitosamente en la base de datos.")


if __name__ == "__main__":
    is_execute = "--execute" in sys.argv
    migrate_data(dry_run=not is_execute)
