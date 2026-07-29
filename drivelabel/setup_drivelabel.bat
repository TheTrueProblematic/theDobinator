@echo off
setlocal EnableDelayedExpansion
title Drive Label - Site Setup

:: ====================================================================
:: setup_drivelabel.bat
::
:: One-shot setup for the Drive Label site (drivelabel.c-nav.com) on the
:: same PC that already hosts theDobinator. Run this ONCE and it will:
::   1. Self-elevate to Administrator (needed for IIS + firewall).
::   2. Create the "Drive Label" IIS site, bound to port 80 with the
::      host header drivelabel.c-nav.com, serving drivelabel\site.
::      theDobinator's own site is left completely untouched — IIS routes
::      by Host header, so both live on port 80 side by side.
::   3. Grant IIS_IUSRS read access to the site folder.
::   4. Open inbound TCP 5051 on the LAN (Private/Domain profiles).
::   5. Register the "Drive Label Web API" scheduled task to auto-launch
::      label_api.py at every logon, running as the logged-in user so it
::      can see the label printer and mapped drives (Z:) — the same
::      deliberate choice api_setup.bat makes for the Dobinator API.
::   6. Start it immediately, so you don't have to reboot.
::   7. Verify both the API health endpoint and the site itself.
::
:: Re-running it is safe (idempotent).
:: ====================================================================

set "SITE_NAME=Drive Label"
set "SITE_HOST=drivelabel.c-nav.com"
set "TASK_NAME=Drive Label Web API"
set "API_PORT=5051"

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
pushd "%SCRIPT_DIR%.."
set "PROJECT_ROOT=%CD%"
popd
set "LOG_DIR=%PROJECT_ROOT%\logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set "LOG_FILE=%LOG_DIR%\drivelabel_setup.log"

set "SITE_DIR=%PROJECT_ROOT%\drivelabel\site"
set "API_BAT=%PROJECT_ROOT%\drivelabel\start_label_api.bat"
set "APPCMD=%windir%\system32\inetsrv\appcmd.exe"

echo %date% %time% - Starting Drive Label setup >> "%LOG_FILE%"
echo %date% %time% - PROJECT_ROOT=%PROJECT_ROOT% >> "%LOG_FILE%"
echo %date% %time% - SITE_DIR=%SITE_DIR% >> "%LOG_FILE%"
echo %date% %time% - API_BAT=%API_BAT% >> "%LOG_FILE%"

echo.
echo =======================================================
echo      Drive Label - Site Setup
echo =======================================================
echo.

if not exist "%SITE_DIR%\index.html" (
    echo [!] Could not find the built site at:
    echo     %SITE_DIR%\index.html
    echo [!] Pull the latest code first - drivelabel\site is committed to
    echo     the repo, so it should already be there.
    echo %date% %time% - ERROR: site not found at %SITE_DIR% >> "%LOG_FILE%"
    pause
    exit /b 1
)

if not exist "%API_BAT%" (
    echo [!] Could not find start_label_api.bat at:
    echo     %API_BAT%
    echo %date% %time% - ERROR: start_label_api.bat not found >> "%LOG_FILE%"
    pause
    exit /b 1
)

if not exist "%APPCMD%" (
    echo [!] IIS does not appear to be installed - appcmd.exe is missing at:
    echo     %APPCMD%
    echo [!] Enable IIS first: Start ^> "Turn Windows features on or off"
    echo     ^> Internet Information Services.
    echo %date% %time% - ERROR: appcmd.exe missing >> "%LOG_FILE%"
    pause
    exit /b 1
)

:: --- 2. Create or update the IIS site --------------------------------
echo [*] Configuring the "%SITE_NAME%" IIS site for %SITE_HOST% ...
echo %date% %time% - Configuring IIS site >> "%LOG_FILE%"

"%APPCMD%" list site "%SITE_NAME%" >nul 2>&1
if %errorLevel% == 0 (
    echo     [i] Site already exists - updating its path and binding.
    echo %date% %time% - Site exists; updating >> "%LOG_FILE%"
    "%APPCMD%" set vdir /vdir.name:"%SITE_NAME%/" /physicalPath:"%SITE_DIR%" >> "%LOG_FILE%" 2>&1
    :: Adding a binding that is already present is a harmless error here.
    "%APPCMD%" set site /site.name:"%SITE_NAME%" /+bindings.[protocol='http',bindingInformation='*:80:%SITE_HOST%'] >> "%LOG_FILE%" 2>&1
) else (
    echo     [i] Creating the site.
    echo %date% %time% - Creating site >> "%LOG_FILE%"
    "%APPCMD%" add site /name:"%SITE_NAME%" /bindings:"http/*:80:%SITE_HOST%" /physicalPath:"%SITE_DIR%" >> "%LOG_FILE%" 2>&1
    if not !errorLevel! == 0 (
        echo [!] Failed to create the IIS site. See %LOG_FILE%
        echo %date% %time% - ERROR: site creation failed >> "%LOG_FILE%"
        pause
        exit /b 1
    )
)

:: --- 3. Folder permissions for IIS -----------------------------------
echo [*] Granting IIS_IUSRS read access to the site folder...
echo %date% %time% - icacls grant IIS_IUSRS >> "%LOG_FILE%"
icacls "%SITE_DIR%" /grant "IIS_IUSRS:(OI)(CI)(RX)" /T /C >> "%LOG_FILE%" 2>&1

echo [*] Starting the site...
"%APPCMD%" start site /site.name:"%SITE_NAME%" >> "%LOG_FILE%" 2>&1

:: --- 4. Firewall: allow inbound 5051 on the LAN ----------------------
echo [*] Opening firewall for TCP %API_PORT% (Private/Domain)...
echo %date% %time% - Creating firewall rule for %API_PORT% >> "%LOG_FILE%"
powershell -NoProfile -Command "if (-not (Get-NetFirewallRule -DisplayName '%TASK_NAME%' -ErrorAction SilentlyContinue)) { New-NetFirewallRule -DisplayName '%TASK_NAME%' -Direction Inbound -Action Allow -Protocol TCP -LocalPort %API_PORT% -Profile Private,Domain | Out-Null }" >> "%LOG_FILE%" 2>&1

:: --- 5. Stop any stale label_api.py (frees port 5051) ----------------
::      Targeted by command line so we DO NOT kill dobd.py, srvr_api.py,
::      or any other python process.
echo [*] Stopping any existing label_api.py instance...
echo %date% %time% - Killing existing label_api.py processes >> "%LOG_FILE%"
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name = 'python.exe' OR Name = 'pythonw.exe'\" | Where-Object { $_.CommandLine -match 'label_api\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >> "%LOG_FILE%" 2>&1

:: --- 6. (Re)register the auto-start scheduled task -------------------
::      onlogon + current user, NOT SYSTEM. The label printer and the
::      mapped Z: drive only exist inside the user's session.
echo [*] Registering "%TASK_NAME%" scheduled task (auto-start at logon)...
echo %date% %time% - Removing any previous task >> "%LOG_FILE%"
schtasks /delete /tn "%TASK_NAME%" /f >> "%LOG_FILE%" 2>&1
echo %date% %time% - Creating task (onlogon, 30s delay) >> "%LOG_FILE%"
schtasks /create /tn "%TASK_NAME%" /tr "\"%API_BAT%\"" /sc onlogon /delay 0000:30 /f >> "%LOG_FILE%" 2>&1
echo %date% %time% - Task creation exit code: %errorLevel% >> "%LOG_FILE%"

schtasks /query /tn "%TASK_NAME%" /v /fo LIST >> "%LOG_FILE%" 2>&1

echo [*] Starting the label API now...
schtasks /run /tn "%TASK_NAME%" >> "%LOG_FILE%" 2>&1

:: --- 7. Verify -------------------------------------------------------
echo [*] Waiting a few seconds for everything to come up...
ping -n 6 127.0.0.1 >nul

echo [*] Checking http://localhost:%API_PORT%/health ...
set "HEALTH_RESP="
set "HEALTH_OK="
for /f "delims=" %%H in ('curl -s -m 5 http://localhost:%API_PORT%/health 2^>nul') do set "HEALTH_RESP=%%H"
echo %date% %time% - Health response: !HEALTH_RESP! >> "%LOG_FILE%"
echo !HEALTH_RESP! | find "ok" >nul 2>&1 && set "HEALTH_OK=1"

:: Hit IIS with the real Host header so this works even before DNS exists.
echo [*] Checking the site through IIS (Host: %SITE_HOST%) ...
set "SITE_CODE="
for /f "delims=" %%S in ('curl -s -o nul -w "%%{http_code}" -m 5 -H "Host: %SITE_HOST%" http://localhost/ 2^>nul') do set "SITE_CODE=%%S"
echo %date% %time% - Site HTTP status: !SITE_CODE! >> "%LOG_FILE%"

echo.
echo =======================================================
if defined HEALTH_OK (
    echo [+] Label API is running on port %API_PORT%.
    echo     Response: !HEALTH_RESP!
    echo [+] It will now start automatically at every logon.
) else (
    echo [!] The API task was registered, but the health check did not
    echo     confirm it is up yet. Response was: !HEALTH_RESP!
    echo [!] Give it a moment, then re-check with:
    echo         curl http://localhost:%API_PORT%/health
    echo [!] If it stays down, check logs\labelApi.log for Python errors.
)
echo.
if "!SITE_CODE!" == "200" (
    echo [+] IIS is serving the site - HTTP 200 for %SITE_HOST%.
    echo [+] Once DNS for %SITE_HOST% points at this PC, the whole
    echo     building can reach it at http://%SITE_HOST%/
) else (
    echo [!] IIS returned HTTP !SITE_CODE! for %SITE_HOST% instead of 200.
    echo     404/403 usually means the physical path or folder permissions
    echo     are wrong. See %LOG_FILE%
)
echo =======================================================
echo.
echo Full setup log: %LOG_FILE%
echo.
pause
endlocal
