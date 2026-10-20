@echo off
REM start.bat — Gas Turbine Engine Simulator startup (Windows)
REM Automatically handles working directory, pre-flight checks, and synchronized browser launch.

cd /d "%~dp0"

echo ========================================================
echo   AETHER-X // GAS TURBINE ENGINE SIMULATOR (v0.5.0)
echo ========================================================
echo   Project Directory: %~dp0
echo.

REM ── Check Python ─────────────────────────────────────────────────────────────
set "PY_CMD="
where python >nul 2>&1
if not errorlevel 1 (
    set "PY_CMD=python"
) else (
    where py >nul 2>&1
    if not errorlevel 1 (
        set "PY_CMD=py"
    )
)

if "%PY_CMD%"=="" (
    echo [ERROR] Python not found in system PATH.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo Ensure "Add Python to PATH" is checked during installation.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('%PY_CMD% --version 2^>^&1') do echo [OK] Python runtime: %%v

REM ── Check/Setup Virtual Environment ─────────────────────────────────────────
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PY_CMD=%~dp0.venv\Scripts\python.exe"
    echo [OK] Using virtual environment: %~dp0.venv
) else (
    REM Check if core dependencies are missing from system Python
    %PY_CMD% -c "import fastapi, uvicorn, pydantic, numpy" >nul 2>&1
    if errorlevel 1 (
        echo [SETUP] Core packages missing. Creating virtual environment in .venv ...
        %PY_CMD% -m venv "%~dp0.venv"
        if not errorlevel 1 (
            echo [SETUP] Installing dependencies from backend\requirements.txt ...
            "%~dp0.venv\Scripts\python.exe" -m pip install -r "%~dp0backend\requirements.txt"
            if not errorlevel 1 (
                set "PY_CMD=%~dp0.venv\Scripts\python.exe"
                echo [OK] Virtual environment initialized.
            )
        )
    )
)

REM ── Check Cantera ─────────────────────────────────────────────────────────────
%PY_CMD% -c "import cantera" >nul 2>&1
if errorlevel 1 (
    echo [NOTICE] Cantera not detected in current Python environment.
    echo   Core engine cycles run natively using high-fidelity NASA-9 polynomials.
    echo   Cantera is optional for standalone oracle cross-validation.
    echo.
) else (
    echo [OK] Cantera verified (Oracle cross-validation available).
)

REM ── Check CF34 Deck ───────────────────────────────────────────────────────────
if not exist "%~dp0data\CF34_deck_v4.csv" (
    echo [WARNING] CF34 deck not found at %~dp0data\CF34_deck_v4.csv
    echo   Turbofan interpolation will not work until the CSV deck is present.
    echo.
) else (
    echo [OK] CF34 performance deck verified.
)

REM ── Check Port 8000 Availability ─────────────────────────────────────────────
%PY_CMD% -c "import socket; s = socket.socket(); s.bind(('127.0.0.1', 8000)); s.close()" >nul 2>&1
if errorlevel 1 (
    echo.
    echo [NOTICE] Port 8000 is currently in use by another process.
    echo   If the simulator is already running in another window, access it at:
    echo   http://localhost:8000/
    echo.
)

REM ── Launch Browser Synchronizer in Background ───────────────────────────────
echo Starting FastAPI backend on http://localhost:8000 ...
echo   Web HUD:     http://localhost:8000/ (v0.5 Obsidian Blueprint)
echo   Legacy HUD:  http://localhost:8000/legacy (v0.4 Reference)
echo   API Docs:    http://localhost:8000/docs
echo.
echo Press Ctrl+C in this window or run stop.bat in another terminal to stop the server.
echo Launching web browser when backend is ready...

set "LAUNCH_PY=%PY_CMD%"
where pythonw >nul 2>&1
if not errorlevel 1 set "LAUNCH_PY=pythonw"

start "" "%LAUNCH_PY%" "%~dp0open_browser.py"

REM ── Run Uvicorn from Backend Directory ──────────────────────────────────────
cd /d "%~dp0backend"
%PY_CMD% -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

if errorlevel 1 (
    echo.
    echo [ERROR] Backend exited with error code %errorlevel%.
    pause
)
