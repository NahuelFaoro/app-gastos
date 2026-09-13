@echo off
setlocal
cd /d "%~dp0\..\.."
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m scripts.validate_project
) else (
    py -m scripts.validate_project
)
if errorlevel 1 pause
