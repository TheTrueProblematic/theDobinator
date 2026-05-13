@echo off
echo Stopping any background instances of dobd.py...

:: Use PowerShell to find and kill the python or pythonw process running dobd.py
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name = 'python.exe' OR Name = 'pythonw.exe'\" | Where-Object { $_.CommandLine -match 'dobd.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"

echo Done!
pause
