@echo off
title The Dobinator - Git Updater Setup

echo [*] Setting up the Git Updater Background Process...

:: Define paths
set "VBS_PATH=%~dp0dobGit.vbs"

:: Kill any existing wscript processes running dobGit.vbs just in case
wmic process where "name='wscript.exe' and commandline like '%%dobGit.vbs%%'" call terminate >nul 2>&1

:: Create the scheduled task to run on system logon
schtasks /create /tn "Dobinator Git Updater" /tr "wscript.exe \"%VBS_PATH%\"" /sc onlogon /delay 0001:00 /f >nul 2>&1

:: Start the process right now
start wscript.exe "%VBS_PATH%"

echo [+] Setup complete! The Dobinator will now automatically update itself every day at 5:00 AM.
