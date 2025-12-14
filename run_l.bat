@echo off
chcp 65001 >nul
title ORA Bot (L: Drive - GPU)
cd /d "%~dp0"
:start
cls
echo 🚀 Launching ORA Bot (L: Drive Environment - GPU Upgrade)
echo ========================================================
echo Checking GPU status...
L:\ORADiscordBOT_Env\Scripts\python.exe -c "import torch; print(f'CUDA Available: {torch.cuda.is_available()}')"
echo.
echo Starting Bot...
L:\ORADiscordBOT_Env\Scripts\python.exe main.py
echo.
echo ========================================================
echo ⚠️ Bot Stopped. Press any key to RESTART.
echo (Close this window to stop completely)
pause
goto start
