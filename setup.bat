@echo off
setlocal EnableDelayedExpansion
title theDobinator Setup

:: Check for Administrator privileges
net session >nul 2>&1
if %errorLevel% == 0 (
    echo Administrator privileges confirmed.
) else (
    echo Requesting Administrator privileges...
    powershell -Command "Start-Process cmd -ArgumentList '/c \"%~dpnx0\"' -Verb RunAs"
    exit /b
)

echo =======================================================
echo          theDobinator - Windows 11 Setup
echo =======================================================
echo.

:: 1. Install Python if not installed
echo [*] Checking for Python...
python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [!] Python not found. Installing Python 3.11 via Winget...
    winget install -e --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements
    
    echo [*] Refreshing environment variables...
    :: Refresh PATH for the current session
    for /f "tokens=2*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path') do set "syspath=%%B"
    for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "userpath=%%B"
    set "PATH=!syspath!;!userpath!"
    
    python --version >nul 2>&1
    if !errorLevel! neq 0 (
        echo [!] Python was installed but the PATH could not be dynamically refreshed.
        echo [!] Please close this window, restart your terminal, and run setup.bat again.
        pause
        exit /b
    )
) else (
    echo [+] Python is already installed.
)

:: 2. Install Python Dependencies
echo.
echo [*] Installing Python Dependencies...
python -m pip install --upgrade pip
python -m pip install "setuptools<70.0.0"
python -m pip install open-interpreter
python -m pip install ipykernel

:: 3. Enable IIS
echo.
echo [*] Enabling Internet Information Services (IIS)...
dism /online /enable-feature /featurename:IIS-WebServerRole /all /norestart >nul

:: 4. Configure IIS Web Portal
echo.
echo [*] Configuring IIS Web Portal...
set "SRVR_DIR=%~dp0srvr"
:: Remove Default Web Site to free up port 80 if it exists
%systemroot%\system32\inetsrv\appcmd delete site "Default Web Site" >nul 2>&1
:: Add Dobinator Portal
%systemroot%\system32\inetsrv\appcmd add site /name:"Dobinator Portal" /id:1 /bindings:http/*:80: /physicalPath:"%SRVR_DIR%" >nul 2>&1
:: Ensure IIS_IUSRS has read & execute permissions on the folder
icacls "%SRVR_DIR%" /grant "IIS_IUSRS:(OI)(CI)RX" /T >nul 2>&1

:: 5. Configure Windows Firewall
echo.
echo [*] Configuring Windows Firewall...
powershell -Command "New-NetFirewallRule -DisplayName 'Dobinator HTTP (IIS)' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 80 -Profile Private,Domain -ErrorAction SilentlyContinue" >nul
powershell -Command "New-NetFirewallRule -DisplayName 'Dobinator Web API' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5050 -Profile Private,Domain -ErrorAction SilentlyContinue" >nul

:: 6. Set up the Companion API (Power Toggle Service) Task
echo.
echo [*] Setting up the Companion API Task...
set "BAT_PATH=%~dp0srvr\start_api.bat"
:: Fix for elevated tasks not seeing mapped network drives (U: and G:)
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" /v EnableLinkedConnections /t REG_DWORD /d 1 /f >nul 2>&1
schtasks /create /tn "Dobinator Web API" /tr "\"%BAT_PATH%\"" /sc onlogon /delay 0000:30 /rl highest /f >nul 2>&1

echo.
echo =======================================================
echo [+] Setup is complete!
echo [+] theDobinator dependencies and system settings are ready.
echo [+] NOTE: A reboot is required for network drive access to apply.
echo =======================================================
echo Press any key to reboot now, or close this window to reboot later...
pause >nul
shutdown /r /t 0
