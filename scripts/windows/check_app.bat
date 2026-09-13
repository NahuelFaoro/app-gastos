@echo off
setlocal
cd /d "%~dp0\..\.."
title App Gastos - Diagnostico
if not exist ".venv\Scripts\python.exe" (
    echo Primero ejecuta start.bat para instalar las dependencias.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m scripts.check_app
if errorlevel 1 (
    echo.
    echo La verificacion encontro un problema.
    pause
    exit /b 1
)
echo.
echo Todo OK.
pause
