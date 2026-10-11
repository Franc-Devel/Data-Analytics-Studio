@echo off
cd /d "%~dp0"
echo Iniciando Dashboard de Consultoria...
if exist ".venv\Scripts\streamlit.exe" (
  ".venv\Scripts\streamlit.exe" run dashboard.py
) else (
  python -m streamlit run dashboard.py
)
pause

