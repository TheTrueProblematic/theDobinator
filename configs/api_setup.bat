@echo off
setlocal EnableDelayedExpansion
title The Dobinator - Companion API Setup

:: ====================================================================
:: api_setup.bat
::
:: One-shot setup for the companion HTTP server (srvr_api.py) that backs
:: the portal's power button AND the new Update button (/update,
:: /schedule-update). Run this ONCE and it will:
::   1. Self-elevate to Administrator (needed for the firewall rule).
::   2. Open inbound TCP 5050 on the LAN (Private/Domain profiles).
::   3. Stop any stale srvr_api.py instance holding port 5050.
::   4. Register the "Dobinator Web API" scheduled task to auto-launch
::      the API at every logon (run as the logged-in user so it can see
::      mapped network drives — matching win_setup.bat's deliberate choice).
::   5. Start it immediately via the task, so you don't have to reboot.
::   6. Verify http://localhost:5050/health responds.
::
:: Re-running it is safe (idempotent): it deletes and recreates the task.
:: ====================================================================

:: --- 1. Ensure we are running as Administrator -----------------------
net session >nul 2>&1
if %errorLevel% == 0 (
    echo [+] Administrator privileges confirmed.
) else (
    echo [*] Requesting Administrator privileges...
    powershell -Command "Start-Process cmd -ArgumentList '/c \"%~dpnx0\"' -Verb RunAs"
    exit /b
)

:: --- Paths + logging -------------------------------------------------
set "SCRIPT_DIR=%~dp0"
set "LOG_DIR=%SCRIPT_DIR%logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set "LOG_FILE=%LOG_DIR%\api_setup.log"

:: Resolve the absolute project root and the start_api.bat path.
pushd "%SCRIPT_DIR%.."
set "PROJECT_ROOT=%CD%"
popd
set "API_BAT=%PROJECT_ROOT%\srvr\start_api.bat"

echo %date% %time% - Starting Companion API setup >> "%LOG_FILE%"
echo %date% %time% - PROJECT_ROOT=%PROJECT_ROOT% >> "%LOG_FILE%"
echo %date% %time% - API_BAT=%API_BAT% >> "%LOG_FILE%"

echo.
echo =======================================================
echo      The Dobinator - Companion API Setup
echo =======================================================
echo.

if not exist "%API_BAT%" (
    echo [!] Could not find start_api.bat at:
    echo     %API_BAT%
    echo [!] Make sure this bat lives in the project's "configs" folder.
    echo %date% %time% - ERROR: start_api.bat not found at %API_BAT% >> "%LOG_FILE%"
    pause
    exit /b 1
)

:: --- 2. Firewall: allow inbound 5050 on the LAN ----------------------
echo [*] Opening firewall for TCP 5050 (Private/Domain)...
echo %date% %time% - Creating firewall rule for 5050 >> "%LOG_FILE%"
powershell -NoProfile -Command "if (-not (Get-NetFirewallRule -DisplayName 'Dobinator Web API' -ErrorAction SilentlyContinue)) { New-NetFirewallRule -DisplayName 'Dobinator Web API' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5050 -Profile Private,Domain | Out-Null }" >> "%LOG_FILE%" 2>&1

:: --- 3. Stop any stale srvr_api.py (frees port 5050) -----------------
::      Targeted by command line so we DO NOT kill dobd.py or other python.
echo [*] Stopping any existing srvr_api.py instance...
echo %date% %time% - Killing existing srvr_api.py processes >> "%LOG_FILE%"
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name = 'python.exe' OR Name = 'pythonw.exe'\" | Where-Object { $_.CommandLine -match 'srvr_api\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >> "%LOG_FILE%" 2>&1

:: --- 4. (Re)register the auto-start scheduled task -------------------
::      onlogon + default (current) user, NOT SYSTEM/elevated, so the API
::      runs in the user's session and can reach mapped network drives.
echo [*] Registering "Dobinator Web API" scheduled task (auto-start at logon)...
echo %date% %time% - Removing any previous Dobinator Web API task >> "%LOG_FILE%"
schtasks /delete /tn "Dobinator Web API" /f >> "%LOG_FILE%" 2>&1
echo %date% %time% - Creating Dobinator Web API task (onlogon, 30s delay) >> "%LOG_FILE%"
schtasks /create /tn "Dobinator Web API" /tr "\"%API_BAT%\"" /sc onlogon /delay 0000:30 /f >> "%LOG_FILE%" 2>&1
echo %date% %time% - Task creation exit code: %errorLevel% >> "%LOG_FILE%"

:: Diagnostic dump for future log diving.
schtasks /query /tn "Dobinator Web API" /v /fo LIST >> "%LOG_FILE%" 2>&1

:: --- 5. Start it now (via the task, so it runs in the right context) --
echo [*] Starting the companion API now...
echo %date% %time% - Running the task now >> "%LOG_FILE%"
schtasks /run /tn "Dobinator Web API" >> "%LOG_FILE%" 2>&1

:: --- 6. Verify it is answering ---------------------------------------
echo [*] Waiting a few seconds for it to come up...
:: Foreground sleep without needing extra tools.
ping -n 6 127.0.0.1 >nul

echo [*] Checking http://localhost:5050/health ...
set "HEALTH_OK="
for /f "delims=" %%H in ('curl -s -m 5 http://localhost:5050/health 2^>nul') do set "HEALTH_RESP=%%H"
echo %date% %time% - Health response: !HEALTH_RESP! >> "%LOG_FILE%"
echo !HEALTH_RESP! | find "ok" >nul 2>&1 && set "HEALTH_OK=1"

echo.
echo =======================================================
if defined HEALTH_OK (
    echo [+] SUCCESS - the companion API is running on port 5050.
    echo     Response: !HEALTH_RESP!
    echo [+] It will now start automatically at every logon.
    echo %date% %time% - SUCCESS: API healthy >> "%LOG_FILE%"
) else (
    echo [!] The API task was registered, but the health check did not
    echo     confirm it is up yet. Response was: !HEALTH_RESP!
    echo [!] Give it a moment, then re-check with:
    echo         curl http://localhost:5050/health
    echo [!] If it stays down, check the log: %LOG_FILE%
    echo     and srvr\srvr_api.log for Python errors.
    echo %date% %time% - WARNING: health check not confirmed >> "%LOG_FILE%"
)
echo =======================================================
echo.
echo Full setup log: %LOG_FILE%
echo.
pause
endlocal
