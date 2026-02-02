:: Request Admin if not running as Admin (Self-elevation)
net session >nul 2>&1
if %errorLevel% == 0 (
    echo Admin privileges confirmed.
) else (
    echo Requesting Admin privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo Killing ORA CMDs (PowerShell)...

:: Refined Filter (Deep Clean):
:: Kills processes where the COMMAND LINE contains 'ora_core', 'src.web', or 'bot.py'.
:: This catches background Python processes that have no window title.

:: Refined Filter (Safe Mode):
:: STRICTLY matches 'ORADiscordBOT' (Folder Name) or 'ora_core' (Module Name).
:: Removes generic 'src.web' or 'cloudflared' matches to protect other user projects.

:: Refined Filter (Surgical Mode):
:: STRICTLY matches the Python Module/Script entry points.
:: - Matches ' -m ora_core' (The Brain)
:: - Matches ' -m src.web' (The Admin Server)
:: - Matches 'bot.py' (The Discord Client)
:: DOES NOT match just the folder path, protecting VSCode/Antigravity extension hosts.

echo Killing ORA Runtime processes (Surgical)...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { ($_.CommandLine -like '* -m ora_core*' -or $_.CommandLine -like '* -m src.web*' -or $_.CommandLine -like '*bot.py*') -and ($_.Name -match 'python') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"

echo Killing ORA Windows (Titles)...
powershell -NoProfile -Command "$targets = @('cmd', 'conhost', 'powershell', 'WindowsTerminal', 'OpenConsole'); Get-Process | Where-Object { ($_.MainWindowTitle -like '*ORA*' -or $_.MainWindowTitle -like '*Tunnel:*' -or $_.MainWindowTitle -like '*next-server*') -and ($targets -contains $_.ProcessName) } | Stop-Process -Force"

echo Cleanup Complete.
timeout /t 2 >nul
exit
