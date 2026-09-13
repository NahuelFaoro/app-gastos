@echo off
setlocal
cd /d "%~dp0\..\.."
if not exist ".venv\Scripts\python.exe" (
  call start.bat
  exit /b
)
".venv\Scripts\python.exe" main.py
if errorlevel 1 pause
