@echo off
chcp 65001 >nul
title ORA Bot (L: Drive - GPU)
cd /d "%~dp0"
:start
cls
echo 🚀 Launching ORA Bot (L: Drive Environment - GPU Upgrade)
echo ========================================================
echo Checking GPU status...
echo Killing previous instances...
taskkill /F /IM python.exe >nul 2>&1

echo Starting ORA Web API...
start "ORA Web API" cmd /k "L:\ORADiscordBOT_Env\Scripts\uvicorn.exe src.web.app:app --reload --port 8000"

echo Starting ORA Vision UI...
start "ORA Vision UI" cmd /k "cd ora-ui && npm run dev"

echo Starting ComfyUI (FLUX.2 Engine)...
start "ComfyUI" cmd /k "cd /d L:\ComfyUI && L:\ORADiscordBOT_Env\Scripts\python.exe main.py --listen 127.0.0.1 --port 8188 --normalvram --disable-cuda-malloc --enable-cors-header * --force-fp16"
timeout /t 5 /nobreak >nul
start http://localhost:8188

echo Starting Bot...
start "ORA Bot" cmd /k "L:\ORADiscordBOT_Env\Scripts\python.exe main.py"

echo ========================================================
echo ✅ All services launched successfully!
echo (You can minimize this window now)
echo.
echo [1] ORA Web API
echo [2] ORA Vision UI
echo [3] Stable Diffusion WebUI
echo [4] ORA Bot
echo.
echo Press any key to stop all services...
echo ========================================================
pause
echo.
echo ========================================================
echo ⚠️ Bot Stopped. Press any key to RESTART.
echo (Close this window to stop completely)
pause
goto start
