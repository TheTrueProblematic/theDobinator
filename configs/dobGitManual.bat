@echo off
setlocal
title The Dobinator - Manual Git Update

set "CONFIGS_DIR=%~dp0"
set "LOG_DIR=%CONFIGS_DIR%logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set "LOG_FILE=%LOG_DIR%\manual.log"
set "PYTHON_SCRIPT=%CONFIGS_DIR%git_updater\git_update.py"
set "GIT_LOG=%CONFIGS_DIR%..\logs\gitLog.log"

echo [*] Triggering manual Git Update...
echo.

echo %date% %time% - Manual trigger started >> "%LOG_FILE%"
echo %date% %time% - Running %PYTHON_SCRIPT% >> "%LOG_FILE%"

python "%PYTHON_SCRIPT%" >> "%LOG_FILE%" 2>&1
set "PY_EXIT=%ERRORLEVEL%"

echo %date% %time% - Python finished with exit code %PY_EXIT% >> "%LOG_FILE%"

echo.
echo --------------------------------------------------------
echo Python exit code: %PY_EXIT%
echo.
if exist "%GIT_LOG%" (
    echo Most recent gitLog entry:
    powershell -NoProfile -Command "Get-Content -Path '%GIT_LOG%' -TotalCount 1"
) else (
    echo No gitLog.log found at %GIT_LOG%
)
echo.
echo Full update log: %CONFIGS_DIR%logs\update.log
echo --------------------------------------------------------
echo.
pause
endlocal
