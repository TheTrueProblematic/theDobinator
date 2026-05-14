@echo off
REM ============================================================
REM The Dobinator - companion API launcher
REM Started by Task Scheduler at boot. See HostingInstructions.md
REM ============================================================
setlocal

REM Resolve paths relative to this script (no matter the cwd)
set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%.."

cd /d "%PROJECT_DIR%"

REM Use pythonw if available so no console window appears
where pythonw >nul 2>nul
if %ERRORLEVEL%==0 (
    start "" /B pythonw "%SCRIPT_DIR%srvr_api.py"
) else (
    start "" /B python  "%SCRIPT_DIR%srvr_api.py"
)

endlocal
