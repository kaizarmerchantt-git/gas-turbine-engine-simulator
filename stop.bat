@echo off
REM stop.bat — Stops AETHER-X backend and frees ports
cd /d "%~dp0"
echo ========================================================
echo   AETHER-X // TERMINATING RUNNING INSTANCES
echo ========================================================
echo Searching for processes listening on port 8000...

set "FOUND="
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do (
    set "FOUND=1"
    echo Terminating process PID %%a ...
    taskkill /F /PID %%a >nul 2>&1
)

if "%FOUND%"=="" (
    echo [INFO] No active simulator processes found on port 8000.
) else (
    echo [OK] AETHER-X server processes terminated. Port 8000 freed.
)
