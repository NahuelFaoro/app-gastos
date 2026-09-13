@echo off
setlocal
cd /d "%~dp0\..\.."

rem APP_VERSION se lee desde la misma fuente usada por la aplicacion.
for /f "tokens=2 delims==" %%A in ('findstr /b /c:"APP_VERSION =" "app\constants.py"') do set "APP_VERSION=%%~A"
set "APP_VERSION=%APP_VERSION:"=%"
set "APP_VERSION=%APP_VERSION: =%"
if not defined APP_VERSION set "APP_VERSION=dev"

echo.
echo ===============================================
echo   App Gastos - Build LITE para compartir
echo ===============================================
echo.
echo Esta build excluye OCR/IA pesada para reducir mucho el peso.
echo El resto de App Gastos funciona normalmente.
echo.

if not exist ".venv\Scripts\python.exe" (
  py -m venv .venv
  if errorlevel 1 exit /b 1
)

".venv\Scripts\python.exe" -m pip install --upgrade pip pyinstaller
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

rmdir /s /q build 2>nul
rmdir /s /q "dist\AppGastos" 2>nul

echo Compilando version LITE...
".venv\Scripts\python.exe" -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --onedir ^
  --name "AppGastos" ^
  --add-data "web;web" ^
  --collect-data qtawesome ^
  --exclude-module PySide6.QtQml ^
  --exclude-module PySide6.QtQuick ^
  --exclude-module PySide6.QtQuickWidgets ^
  --exclude-module PySide6.QtPdf ^
  --exclude-module PySide6.QtPdfWidgets ^
  --exclude-module PySide6.QtWebEngineCore ^
  --exclude-module PySide6.QtWebEngineWidgets ^
  --exclude-module rapidocr ^
  --exclude-module onnxruntime ^
  --exclude-module cv2 ^
  --exclude-module fitz ^
  --exclude-module pymupdf ^
  --exclude-module numpy ^
  main.py
if errorlevel 1 exit /b 1

rem Qt incluye traducciones/plugins que esta app no utiliza. Limpiarlos reduce
rem bastante el ZIP sin afectar Widgets/Core/Gui usados por App Gastos.
if exist "dist\AppGastos\_internal\PySide6\translations" rmdir /s /q "dist\AppGastos\_internal\PySide6\translations"
if exist "dist\AppGastos\_internal\PySide6\qml" rmdir /s /q "dist\AppGastos\_internal\PySide6\qml"

set "OUT=dist\AppGastos_v%APP_VERSION%_LITE.zip"
if exist "%OUT%" del /q "%OUT%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'dist\AppGastos\*' -DestinationPath '%OUT%' -CompressionLevel Optimal"
if errorlevel 1 exit /b 1

echo.
echo Listo para compartir:
echo %CD%\%OUT%
echo.
for %%A in ("%OUT%") do echo Tamano: %%~zA bytes
pause
