@echo off
setlocal EnableDelayedExpansion
title The Dobinator - Updater Setup

set "LOG_DIR=%~dp0logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set "LOG_FILE=%LOG_DIR%\setup.log"

echo %date% %time% - Starting Updater Setup >> "%LOG_FILE%"
echo [*] Setting up the Updater Background Process...

:: --------------------------------------------------------------------
:: 1. Ensure Git is installed. If not, install it via winget.
:: --------------------------------------------------------------------
echo %date% %time% - Checking for Git >> "%LOG_FILE%"
where git >nul 2>&1
if %errorLevel% neq 0 (
    echo [!] Git not found. Installing Git via Winget...
    echo %date% %time% - Git not found, attempting winget install Git.Git >> "%LOG_FILE%"
    winget install -e --id Git.Git --accept-package-agreements --accept-source-agreements >> "%LOG_FILE%" 2>&1
    echo %date% %time% - winget exit code: !errorLevel! >> "%LOG_FILE%"

    :: Winget updates PATH at the user/machine level but the current process
    :: doesn't see it. Re-read PATH from the registry into this session so
    :: subsequent "where git" succeeds.
    for /f "tokens=2*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path') do set "syspath=%%B"
    for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "userpath=%%B"
    set "PATH=!syspath!;!userpath!"

    where git >nul 2>&1
    if !errorLevel! neq 0 (
        echo [!] Git installation finished but git is still not on PATH for this session.
        echo [!] Sign out / sign in or reboot so the new PATH is picked up, then re-run win_setup.bat.
        echo %date% %time% - Git still not resolvable after install. Continuing setup anyway. >> "%LOG_FILE%"
    ) else (
        echo [+] Git is now installed and on PATH.
        echo %date% %time% - Git resolvable after install. >> "%LOG_FILE%"
    )
) else (
    echo [+] Git is already installed.
    echo %date% %time% - Git already on PATH. >> "%LOG_FILE%"
)

:: Capture and log git version for diagnostics.
for /f "delims=" %%V in ('git --version 2^>^&1') do set "GIT_VER=%%V"
echo %date% %time% - !GIT_VER! >> "%LOG_FILE%"

:: --------------------------------------------------------------------
:: 2. Mark the project root as a safe directory for Git globally so the
::    daemon-context updater (and other users) don't trip the "dubious
::    ownership" refusal on newer Git versions.
:: --------------------------------------------------------------------
set "PROJECT_ROOT=%~dp0.."
pushd "%PROJECT_ROOT%"
set "PROJECT_ROOT_ABS=%CD%"
popd
:: Convert backslashes to forward slashes (Git's preferred form).
set "PROJECT_ROOT_GIT=!PROJECT_ROOT_ABS:\=/!"
echo %date% %time% - Adding safe.directory: !PROJECT_ROOT_GIT! >> "%LOG_FILE%"
git config --global --add safe.directory "!PROJECT_ROOT_GIT!" >> "%LOG_FILE%" 2>&1

:: --------------------------------------------------------------------
:: 3. Kill any pre-existing dobGit.vbs watcher so we don't end up with
::    duplicates after re-running setup.
:: --------------------------------------------------------------------
set "VBS_PATH=%~dp0dobGit.vbs"
echo %date% %time% - VBS_PATH is %VBS_PATH% >> "%LOG_FILE%"

echo %date% %time% - Killing any existing wscript processes running dobGit.vbs >> "%LOG_FILE%"
:: wmic was removed by default on Windows 11. Use PowerShell to find and
:: terminate any wscript.exe whose command line references dobGit.vbs.
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name = 'wscript.exe'\" | Where-Object { $_.CommandLine -match 'dobGit\.vbs' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >> "%LOG_FILE%" 2>&1

:: --------------------------------------------------------------------
:: 4. Create a scheduled task that re-launches the VBS watcher on every
::    logon. The VBS itself is what waits until 5 AM each day; the task
::    just makes sure the watcher survives reboots.
:: --------------------------------------------------------------------
echo %date% %time% - Creating scheduled task >> "%LOG_FILE%"
schtasks /create /tn "Dobinator Git Updater" /tr "wscript.exe \"%VBS_PATH%\"" /sc onlogon /delay 0001:00 /f >> "%LOG_FILE%" 2>&1
echo %date% %time% - Task creation exit code: %errorLevel% >> "%LOG_FILE%"

:: --------------------------------------------------------------------
:: 5. Start the VBS watcher right now so we don't have to wait for the
::    next logon.
:: --------------------------------------------------------------------
echo %date% %time% - Starting dobGit.vbs now >> "%LOG_FILE%"
start "" wscript.exe "%VBS_PATH%"

echo %date% %time% - Setup script completed >> "%LOG_FILE%"
echo [+] Setup complete! The Dobinator will now automatically update itself every day at 5:00 AM.
endlocal
