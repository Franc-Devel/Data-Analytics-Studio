@echo off
setlocal
cd /d "%~dp0"

echo =========================================================
echo    Nexo Analytics - Commercial & CRM Intelligence Suite
echo =========================================================
echo.

if exist ".venv\Scripts\streamlit.exe" (
  echo [INFO] Iniciando Web App con entorno virtual .venv en http://localhost:8501 ...
  ".venv\Scripts\streamlit.exe" run dashboard.py
  goto :end
)

where py >nul 2>nul
if %errorlevel%==0 (
  py -c "import streamlit, pandas, openpyxl, sqlalchemy, bcrypt" >nul 2>nul
  if errorlevel 1 (
    echo [INFO] Instalando dependencias necesarias...
    py -m pip install -r requirements.txt
    if errorlevel 1 goto :install_error
  )
  echo [INFO] Iniciando Web App en http://localhost:8501 ...
  py -m streamlit run dashboard.py
  goto :end
)

where python >nul 2>nul
if %errorlevel%==0 (
  python -c "import streamlit, pandas, openpyxl, sqlalchemy, bcrypt" >nul 2>nul
  if errorlevel 1 (
    echo [INFO] Instalando dependencias necesarias...
    python -m pip install -r requirements.txt
    if errorlevel 1 goto :install_error
  )
  echo [INFO] Iniciando Web App en http://localhost:8501 ...
  python -m streamlit run dashboard.py
  goto :end
)

echo [ERROR] No se encontro Python. Instale Python 3.11 o superior desde python.org.
pause
goto :end

:install_error
echo.
echo [ERROR] No se pudieron instalar las dependencias.
echo Revise su conexion a Internet y vuelva a ejecutar iniciar.bat.
pause

:end
endlocal
