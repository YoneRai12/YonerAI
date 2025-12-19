@echo off
setlocal
cd /d "%~dp0"

echo ===================================================
echo     Launching Training in WSL (Ubuntu-22.04)
echo ===================================================

REM Convert Windows Path to WSL Path is tricky with sed/wslpath if not inside WSL.
REM Hardcoding known path for robustness based on user status.
REM Path: /mnt/c/Users/YoneRai12/Desktop/ORADiscordBOT-main3/RTX5090-DebugSystem-main/train_wsl.sh

wsl -d Ubuntu-22.04 -u root -- bash /mnt/c/Users/YoneRai12/Desktop/ORADiscordBOT-main3/RTX5090-DebugSystem-main/train_wsl.sh

pause
