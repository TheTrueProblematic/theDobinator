@echo off
echo Stopping any background instances of dobd.py...

:: Use PowerShell to find and kill the python or pythonw process running dobd.py
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name = 'python.exe' OR Name = 'pythonw.exe'\" | Where-Object { $_.CommandLine -match 'dobd.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"

:: Update status.json to reflect that the program is no longer running
powershell -NoProfile -Command "$path = '%~dp0..\srvr\status.json'; if (Test-Path $path) { $json = Get-Content $path | ConvertFrom-Json; $json.Running = 0; $json | ConvertTo-Json -Depth 10 | Set-Content $path }"

echo Done!
pause
