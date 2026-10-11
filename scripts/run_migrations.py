"""
Nexo Analytics - Runner Unificado de Migraciones de Base de Datos
Ejecuta migraciones declarativas mediante Alembic (si está disponible) o el motor interno de auto-migración.

Uso:
  python scripts/run_migrations.py
  python scripts/run_migrations.py --check
"""

import sys
from pathlib import Path

# Añadir raíz al sys.path
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

from finance_app.db.session import get_engine, init_db
from finance_app.db.migrations import run_auto_migrations
from finance_app.config import get_config


def main():
    cfg = get_config()
    print("=" * 70)
    print(" [*] NEXO ANALYTICS - GESTOR DE MIGRACIONES DE BASE DE DATOS")
    print("=" * 70)
    print(f"Base de Datos Objetivo: {cfg.database_url}\n")

    engine = get_engine()
    init_db()
    count = run_auto_migrations(engine)
    print(f"[OK] Verificacion de esquema completada ({count} columnas migradas).")


if __name__ == "__main__":
    main()
