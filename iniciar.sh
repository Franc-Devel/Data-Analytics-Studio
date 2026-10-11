#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

# Asegurar Node.js y binarios en el PATH
export PATH="$HOME/.local/share/mise/shims:$HOME/.local/bin:$HOME/.local/node/bin:$PATH"

echo "========================================================="
echo "   Nexo Analytics - Commercial & CRM Intelligence Suite"
echo "========================================================="
echo ""

# Verificar y activar entorno virtual disponible
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
elif [ -f ".venv_linux/bin/activate" ]; then
    source .venv_linux/bin/activate
else
    echo "[INFO] Creando entorno virtual .venv_linux..."
    python3 -m venv .venv_linux
    source .venv_linux/bin/activate
fi

# Verificar si las dependencias principales están instaladas, si no instalarlas
if ! python3 -c "import streamlit, pandas, openpyxl, sqlalchemy, bcrypt, cryptography" &> /dev/null; then
    echo "[INFO] Instalando dependencias desde requirements.txt..."
    pip install -r requirements.txt
fi

echo "[INFO] Iniciando Web App en http://localhost:8501 ..."
python3 -m streamlit run dashboard.py

