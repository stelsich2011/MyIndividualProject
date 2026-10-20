@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo First install: py -3 -m venv .venv
    echo Then: .venv\Scripts\python.exe -m pip install -e ".[desktop]"
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m oge_checker.desktop %*
if errorlevel 1 pause
