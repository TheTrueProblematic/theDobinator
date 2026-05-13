@echo off
echo Checking dobd.py background process status...

:: Use PowerShell to determine if dobd.py is currently running
powershell -NoProfile -Command "$proc = Get-CimInstance Win32_Process -Filter \"Name = 'python.exe' OR Name = 'pythonw.exe'\" | Where-Object { $_.CommandLine -match 'dobd.py' }; if ($proc) { exit 0 } else { exit 1 }"

if %errorlevel% equ 0 (
    echo.
    echo Process found! It is currently running.
    echo Handing over to quit.bat to terminate it...
    echo.
    call src\quit.bat
) else (
    echo.
    echo Process not found. It is not currently running.
    echo Handing over to dobr.vbs to start it...
    wscript src\dobr.vbs
    echo.
    echo Successfully started dobd.py in the background!
    pause
)
