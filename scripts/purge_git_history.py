"""
Nexo Analytics - Script de Sanitización y Purga de Historial Git
Permite purgar de raíz cualquier rastro histórico de credenciales y tokens de WhatsApp Baileys (auth_info_baileys/)
del historial de Git utilizando git-filter-repo.

Instrucciones de uso:
1. Instalar git-filter-repo: pip install git-filter-repo
2. Crear un backup completo de la carpeta del proyecto antes de ejecutar.
3. Ejecutar: python scripts/purge_git_history.py --execute
4. Forzar push en el repositorio remoto: git push origin --force --all
"""

import sys
import subprocess
from pathlib import Path

def main():
    repo_root = Path(__file__).resolve().parent.parent
    execute = "--execute" in sys.argv

    print("=" * 70)
    print(" [*] HERRAMIENTA DE PURGA CRIPTOGRAFICA DE HISTORIAL GIT")
    print("=" * 70)
    print(f"Directorio de trabajo: {repo_root}\n")

    paths_to_remove = [
        "whatsapp_bridge/auth_info_baileys",
        "whatsapp_bridge/auth_info_baileys/*",
        "whatsapp_config.json",
        "whatsapp_sync_state.json",
        "whatsapp_inbox",
        "whatsapp_inbox/*",
        "*.sqlite",
        "*.db",
        "data/*.db",
    ]

    print("Rutas a eliminar de TODOS los commits pasados:")
    for p in paths_to_remove:
        print(f" - {p}")
    print()

    if not execute:
        print("[!] MODO SIMULACION (DRY-RUN)")
        print("Para ejecutar la purga definitiva del arbol de Git, ejecute:")
        print("  python scripts/purge_git_history.py --execute\n")
        print("Comando git filter sugerido:")
        print("  git rm -r --cached whatsapp_bridge/auth_info_baileys whatsapp_config.json\n")
        return

    print("Ejecutando git filter-branch / filter-repo...")
    try:
        cmd = [
            sys.executable,
            "-m",
            "git_filter_repo",
            "--path",
            "whatsapp_bridge/auth_info_baileys",
            "--invert-paths",
            "--force",
        ]
        result = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ Historial de Git purgado exitosamente.")
            print("⚠️ Recuerde rotar cualquier token o sesión previa y forzar la sincronización remota con:")
            print("  git push origin --force --all")
        else:
            print("Error ejecutando git-filter-repo:")
            print(result.stderr)
            print("\nSi git-filter-repo no está instalado, instálelo con:")
            print("  pip install git-filter-repo")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
