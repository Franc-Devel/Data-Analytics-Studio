"""
Nexo Analytics - Motor de Auto-Migraciones de Esquema de Base de Datos
Inspecciona automáticamente bases de datos SQLite y PostgreSQL existentes y aplica sentencias
ALTER TABLE seguras para agregar nuevas columnas sin pérdida de datos ni necesidad de recrear la BD.
"""

from __future__ import annotations
from typing import Optional, List, Dict, Tuple
from sqlalchemy import inspect, text, Engine

from finance_app.logging_config import get_logger

logger = get_logger("db.migrations")

# Definición de migraciones esperadas por tabla y tipo SQL
TABLE_COLUMN_SPECS: Dict[str, List[Tuple[str, str]]] = {
    "users": [
        ("failed_login_attempts", "INTEGER DEFAULT 0 NOT NULL"),
        ("locked_until", "DATETIME"),
        ("must_change_password", "BOOLEAN DEFAULT 0 NOT NULL"),
        ("mfa_secret", "VARCHAR(512)"),
        ("mfa_enabled", "BOOLEAN DEFAULT 0 NOT NULL"),
        ("mfa_recovery_codes_hash", "TEXT"),
        ("last_totp_code_used", "VARCHAR(10)"),
        ("session_token_version", "INTEGER DEFAULT 1 NOT NULL"),
        ("password_changed_at", "DATETIME"),
        ("last_login", "DATETIME"),
    ],
    "customers": [
        ("phone_blind_index", "VARCHAR(64)"),
        ("name_blind_index", "VARCHAR(64)"),
        ("name_tokens_index", "TEXT"),
        ("phone_tokens_index", "TEXT"),
        ("document_id", "VARCHAR(512)"),
        ("locality", "VARCHAR(100)"),
        ("region", "VARCHAR(80)"),
        ("product_line", "VARCHAR(80)"),
        ("lead_score", "INTEGER DEFAULT 50 NOT NULL"),
        ("segment", "VARCHAR(30) DEFAULT 'WARM' NOT NULL"),
        ("status", "VARCHAR(40) DEFAULT 'NUEVO' NOT NULL"),
        ("next_follow_up_at", "DATETIME"),
        ("total_contacts", "INTEGER DEFAULT 1 NOT NULL"),
    ],
    "audit_logs": [
        ("prev_hash", "VARCHAR(64)"),
        ("entry_hash", "VARCHAR(64)"),
        ("ip_address", "VARCHAR(45)"),
    ],
    "whatsapp_queue": [
        ("attempts", "INTEGER DEFAULT 0 NOT NULL"),
        ("max_attempts", "INTEGER DEFAULT 3 NOT NULL"),
        ("next_retry_at", "DATETIME"),
        ("sent_at", "DATETIME"),
        ("last_error", "TEXT"),
    ],
}


def run_auto_migrations(engine: Engine) -> int:
    """
    Inspecciona todas las tablas de la base de datos y agrega cualquier columna faltante.
    Retorna la cantidad de columnas migradas.
    """
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    migrated_count = 0

    with engine.begin() as conn:
        for table_name, columns_spec in TABLE_COLUMN_SPECS.items():
            if table_name not in existing_tables:
                continue

            existing_cols = {c["name"] for c in inspector.get_columns(table_name)}

            for col_name, col_type_sql in columns_spec:
                if col_name not in existing_cols:
                    logger.warning(f"Migración: Agregando columna faltante '{col_name}' en tabla '{table_name}'...")
                    try:
                        alter_query = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type_sql}"
                        conn.execute(text(alter_query))
                        migrated_count += 1
                        logger.info(f"[OK] Columna '{col_name}' agregada con exito a '{table_name}'.")
                    except Exception as e:
                        logger.error(f"Error aplicando migracion '{col_name}' en '{table_name}': {e}")

    if migrated_count > 0:
        logger.info(f"Auto-migracion completada: {migrated_count} columnas actualizadas en la base de datos.")
    return migrated_count
