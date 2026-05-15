@echo off
title The Dobinator - Git Updater Setup

set "LOG_DIR=%~dp0logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set "LOG_FILE=%LOG_DIR%\setup.log"

echo %date% %time% - Starting Git Updater Setup >> "%LOG_FILE%"
echo [*] Setting up the Git Updater Background Process...

echo.
echo %date% %time% - Defining VBS_PATH >> "%LOG_FILE%"
:: Define paths
set "VBS_PATH=%~dp0dobGit.vbs"
echo %date% %time% - VBS_PATH is %VBS_PATH% >> "%LOG_FILE%"

echo %date% %time% - Killing any existing wscript processes running dobGit.vbs >> "%LOG_FILE%"
wmic process where "name='wscript.exe' and commandline like '%%dobGit.vbs%%'" call terminate >> "%LOG_FILE%" 2>&1

echo %date% %time% - Creating scheduled task >> "%LOG_FILE%"
schtasks /create /tn "Dobinator Git Updater" /tr "wscript.exe \"%VBS_PATH%\"" /sc onlogon /delay 0001:00 /f >> "%LOG_FILE%" 2>&1
echo %date% %time% - Task creation exit code: %errorlevel% >> "%LOG_FILE%"

echo %date% %time% - Starting dobGit.vbs right now >> "%LOG_FILE%"
start wscript.exe "%VBS_PATH%"
echo %date% %time% - Setup script completed >> "%LOG_FILE%"

echo [+] Setup complete! The Dobinator will now automatically update itself every day at 5:00 AM.
