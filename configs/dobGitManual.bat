@echo off
title The Dobinator - Manual Git Update

set "LOG_DIR=%~dp0git_updater\logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set "LOG_FILE=%LOG_DIR%\manual.log"

echo %date% %time% - Manual trigger started >> "%LOG_FILE%"
echo [*] Triggering manual Git Update...
echo.

set "PYTHON_SCRIPT=%~dp0git_updater\git_update.py"
echo %date% %time% - Running python script: %PYTHON_SCRIPT% >> "%LOG_FILE%"

python "%PYTHON_SCRIPT%" >> "%LOG_FILE%" 2>&1

echo %date% %time% - Python script finished with exit code %errorlevel% >> "%LOG_FILE%"
echo.
echo [+] Update process finished. Check logs/gitLog.log for details.
pause
