@echo off
REM start.bat — Gas Turbine Engine Simulator startup (Windows)
REM Run from the project root: start.bat

echo ========================================
echo   Gas Turbine Engine Simulator
echo ========================================
echo.

REM ── Check Python ─────────────────────────────────────────────────────────────
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: python not found.
    echo Install Python 3.10+ from https://www.python.org/downloads/
    pause
    exit /b 1
)
python --version

REM ── Check Cantera ─────────────────────────────────────────────────────────────
python -c "import cantera" >nul 2>&1
if errorlevel 1 (
    echo.
    echo WARNING: Cantera not found in current Python environment.
    echo   Option A ^(pip^):   pip install cantera==3.0.0
    echo   Option B ^(conda^): conda install -c conda-forge cantera=3.0.0
    echo.
    echo   The TURBOFAN model will still work without Cantera.
    echo   See SETUP_GUIDE.md for full instructions.
    echo.
)

REM ── Check CF34 deck ───────────────────────────────────────────────────────────
if not exist "data\CF34_deck_v4.csv" (
    echo WARNING: CF34 deck not found at data\CF34_deck_v4.csv
    echo   Turbofan interpolation will not work.
    echo   Copy CF34_deck_v4.csv from the repository into the data\ folder.
    echo.
)

REM ── Start backend ─────────────────────────────────────────────────────────────
echo Starting FastAPI backend on http://localhost:8000 ...
echo   API docs: http://localhost:8000/docs
echo.
echo   Open frontend\index.html in your browser to use the simulator.
echo   Press CTRL+C to stop.
echo.

cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pause
