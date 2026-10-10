@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
  py -c "import pandas, openpyxl, customtkinter, matplotlib, seaborn" >nul 2>nul
  if errorlevel 1 (
    echo Instalando componentes necesarios...
    py -m pip install -r requirements.txt
    if errorlevel 1 goto :install_error
  )
  py run_app.py
  goto :end
)

where python >nul 2>nul
if %errorlevel%==0 (
  python -c "import pandas, openpyxl, customtkinter, matplotlib, seaborn" >nul 2>nul
  if errorlevel 1 (
    echo Instalando componentes necesarios...
    python -m pip install -r requirements.txt
    if errorlevel 1 goto :install_error
  )
  python run_app.py
  goto :end
)

echo No se encontro Python. Instale Python 3.11 o superior desde python.org.
pause
goto :end

:install_error
echo.
echo No se pudieron instalar las dependencias.
echo Revise el mensaje anterior y luego ejecute nuevamente iniciar.bat.
pause

:end
endlocal

