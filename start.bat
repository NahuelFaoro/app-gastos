@echo off
setlocal
cd /d "%~dp0"
title App Gastos

rem APP_VERSION tiene una sola fuente de verdad en app\constants.py.
for /f "tokens=2 delims==" %%A in ('findstr /b /c:"APP_VERSION =" "app\constants.py"') do set "APP_VERSION=%%~A"
set "APP_VERSION=%APP_VERSION:"=%"
set "APP_VERSION=%APP_VERSION: =%"
if not defined APP_VERSION set "APP_VERSION=desconocida"

echo.
echo ========================================
echo             APP GASTOS v%APP_VERSION%
echo ========================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Primera ejecucion: creando entorno virtual...
    py -m venv .venv
    if errorlevel 1 goto :error
)

".venv\Scripts\python.exe" -m ensurepip --upgrade >nul 2>&1
rem La instalacion normal incluye tambien el motor OCR para tickets y resumenes.
".venv\Scripts\python.exe" -c "import PySide6, openpyxl, qtawesome, requests, keyring, rapidocr, onnxruntime, fitz" >nul 2>&1
if errorlevel 1 (
    echo Instalando o actualizando dependencias, incluido OCR. La primera vez puede tardar unos minutos...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    if errorlevel 1 goto :error
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt -r requirements-ocr.txt
    if errorlevel 1 goto :error
    ".venv\Scripts\python.exe" -c "import PySide6, openpyxl, qtawesome, requests, keyring, rapidocr, onnxruntime, fitz" >nul 2>&1
    if errorlevel 1 (
        echo.
        echo ERROR: las dependencias se instalaron pero el motor OCR no pudo cargarse.
        echo Copiame el texto de esta ventana para revisarlo.
        goto :error
    )
)

set "SMOKE_DIR=%APPDATA%\AppGastos"
set "SMOKE_MARKER=%SMOKE_DIR%\.smoke_v%APP_VERSION%"
if not exist "%SMOKE_MARKER%" (
    if not exist "%SMOKE_DIR%" mkdir "%SMOKE_DIR%" >nul 2>&1
    echo Verificando integridad de esta version por unica vez...
    ".venv\Scripts\python.exe" -m scripts.check_app
    if errorlevel 1 (
        echo.
        echo ERROR: la verificacion preventiva encontro un problema real.
        echo Para evitar abrir una version rota, App Gastos no continuara.
        echo Copiame el error que aparece arriba para corregirlo.
        goto :error
    ) else (
        >"%SMOKE_MARKER%" echo ok
    )
)

".venv\Scripts\python.exe" main.py
if errorlevel 1 goto :error
exit /b 0

:error
echo.
echo La aplicacion encontro un error.
echo Copiame el texto de esta ventana si no sabes como resolverlo.
echo.
pause
exit /b 1
