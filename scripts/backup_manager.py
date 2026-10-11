"""
Script CLI para administración de Backups y Recuperación de Datos de Nexo Analytics.
Uso:
  python scripts/backup_manager.py backup
  python scripts/backup_manager.py list
  python scripts/backup_manager.py restore <backup_file> <target_file>
  python scripts/backup_manager.py backup-session
"""

import sys
import argparse
from pathlib import Path

# Agregar raíz al sys.path para permitir importar finance_app
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from finance_app.config import get_config
from finance_app.backup_manager import (
    create_backup,
    list_backups,
    restore_backup,
    backup_whatsapp_session,
)


def main():
    parser = argparse.ArgumentParser(description="Administrador de Backups de Nexo Analytics")
    subparsers = parser.add_subparsers(dest="command", help="Comando a ejecutar")

    # Comando backup
    backup_parser = subparsers.add_parser("backup", help="Crear backup de las bases de datos")
    backup_parser.add_argument("--tag", default="manual_cli", help="Etiqueta para el backup")

    # Comando list
    list_parser = subparsers.add_parser("list", help="Listar backups existentes")
    list_parser.add_argument("--prefix", default=None, help="Filtrar por prefijo de archivo")

    # Comando restore
    restore_parser = subparsers.add_parser("restore", help="Restaurar un archivo desde backup")
    restore_parser.add_argument("backup_file", help="Ruta al archivo de backup")
    restore_parser.add_argument("target_file", help="Ruta destino donde restaurar")

    # Comando backup-session
    subparsers.add_parser("backup-session", help="Crear archivo zip de la sesión de WhatsApp Baileys")

    args = parser.parse_args()
    cfg = get_config()

    if args.command == "backup":
        print("[INFO] Generando copias de seguridad...")
        leads_path = cfg.resolve_leads_path()
        comm_path = cfg.resolve_commercial_path()
        
        if leads_path.exists():
            res1 = create_backup(leads_path, tag=args.tag)
            print(f"  * Leads: {res1.name if res1 else 'Error'}")
        if comm_path.exists():
            res2 = create_backup(comm_path, tag=args.tag)
            print(f"  * Comercial: {res2.name if res2 else 'Error'}")

    elif args.command == "list":
        backups = list_backups(file_prefix=args.prefix)
        print(f"\n[INFO] Backups disponibles en '{cfg.backup_dir}' ({len(backups)} archivos):")
        print("-" * 75)
        print(f"{'FECHA':<20} | {'TAMANO (KB)':<12} | {'ARCHIVO'}")
        print("-" * 75)
        for b in backups:
            print(f"{b['created_at']:<20} | {b['size_kb']:<12} | {b['filename']}")
        print("-" * 75)

    elif args.command == "restore":
        print(f"[INFO] Restaurando {args.backup_file} -> {args.target_file}...")
        success = restore_backup(args.backup_file, args.target_file)
        if success:
            print("  * Restauracion exitosa.")
        else:
            print("  ! Error durante la restauracion.")
            sys.exit(1)

    elif args.command == "backup-session":
        print("[INFO] Respaldando sesion de WhatsApp...")
        res = backup_whatsapp_session()
        if res:
            print(f"  * Sesion respaldada en: {res.name}")
        else:
            print("  ! No se pudo respaldar la sesion (directorio vacio o no encontrado).")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
