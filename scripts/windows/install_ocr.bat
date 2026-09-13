@echo off
setlocal
cd /d "%~dp0\..\.."
if not exist ".venv\Scripts\python.exe" py -m venv .venv
".venv\Scripts\python.exe" -m ensurepip --upgrade
".venv\Scripts\python.exe" -m pip install -r requirements-ocr.txt
if errorlevel 1 goto :error
echo.
echo OCR opcional instalado correctamente.
pause
exit /b 0
:error
echo.
echo No se pudo instalar el OCR opcional.
pause
exit /b 1
