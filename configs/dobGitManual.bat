@echo off
title The Dobinator - Manual Git Update

echo [*] Triggering manual Git Update...
echo.

set "PYTHON_SCRIPT=%~dp0git_updater\git_update.py"

python "%PYTHON_SCRIPT%"

echo.
echo [+] Update process finished. Check logs/gitLog.log for details.
pause
