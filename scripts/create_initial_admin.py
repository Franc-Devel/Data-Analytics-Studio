"""
Nexo Analytics - Script CLI de Inicialización Segura del Administrador
Permite crear o restablecer la cuenta de superadministrador con contraseñas de alta entropía.

Uso:
    python scripts/create_initial_admin.py
    python scripts/create_initial_admin.py --username admin --email admin@consultora.com --password "MiSuperClave#2026!"
"""

import argparse
import sys
from pathlib import Path

# Asegurar raíz del proyecto en sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from finance_app.db.session import get_db_session, init_db
from finance_app.db.auth_service import setup_initial_admin, validate_password_strength


def main():
    parser = argparse.ArgumentParser(description="Inicialización segura de superadministrador de Nexo Analytics.")
    parser.add_argument("--username", default="admin", help="Nombre de usuario del administrador (default: admin)")
    parser.add_argument("--email", default="admin@consultora.com", help="Email del administrador")
    parser.add_argument("--fullname", default="Administrador Corporativo", help="Nombre completo")
    parser.add_argument("--password", default=None, help="Contraseña específica (si no se especifica, se genera una aleatoria de 16 caracteres)")

    args = parser.parse_args()

    if args.password:
        is_strong, err = validate_password_strength(args.password)
        if not is_strong:
            print(f"\n❌ Error de validación: {err}")
            sys.exit(1)

    print("\n=======================================================")
    print("◈ NEXO ANALYTICS - SETUP INICIAL DE ADMINISTRADOR")
    print("=======================================================")

    init_db()

    with get_db_session() as session:
        user, pwd = setup_initial_admin(
            session=session,
            username=args.username,
            email=args.email,
            full_name=args.fullname,
            plain_password=args.password,
        )
        username = user.username
        email = user.email
        session.commit()

    print("\n✅ Superadministrador configurado exitosamente.")
    print(f"👤 Usuario:    {username}")
    print(f"✉️  Email:      {email}")
    print(f"🔑 Contraseña: {pwd}")
    print("⚠️  AVISO DE SEGURIDAD: Guarde esta contraseña de forma segura en su gestor de credenciales.")
    print("    El sistema solicitará el cambio obligatorio de contraseña en el primer inicio de sesión.\n")


if __name__ == "__main__":
    main()
