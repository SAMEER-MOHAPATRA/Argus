@echo off
rem Argus.bat — double-click to start. Makes the venv on first run, then opens the page.
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo First run: setting up Python environment...
    where py >nul 2>nul && (py -3 -m venv .venv) || (python -m venv .venv)
    if not exist ".venv\Scripts\python.exe" (
        echo.
        echo Python was not found. Install it from https://www.python.org/downloads/
        echo and tick "Add python.exe to PATH" in the installer. Then run Argus.bat again.
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check -r requirements.txt
)

".venv\Scripts\python.exe" dashboard.py
if errorlevel 1 pause
