@echo off
:: Check for administrative permissions
net session >nul 2>&1
if %errorLevel% == 0 (
    goto :run
) else (
    echo Requesting administrative privileges...
    powershell -Command "Start-Process -FilePath '%~dpnx0' -Verb RunAs"
    exit /b
)

:run
:: Change to the directory where the batch file is located
cd /d "%~dp0"

echo Running dobd.py as Administrator...
python dobd.py
pause
