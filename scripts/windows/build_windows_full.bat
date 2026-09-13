@echo off
setlocal
cd /d "%~dp0\..\.."
echo Build completa con OCR opcional. Puede ocupar bastante mas espacio.
if not exist ".venv\Scripts\python.exe" py -m venv .venv
".venv\Scripts\python.exe" -m pip install --upgrade pip pyinstaller
".venv\Scripts\python.exe" -m pip install -r requirements.txt -r requirements-ocr.txt
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --windowed --onedir --name "AppGastos" --add-data "web;web" --collect-all qtawesome --collect-all rapidocr main.py
if errorlevel 1 exit /b 1
echo Listo en dist\AppGastos\AppGastos.exe
pause
