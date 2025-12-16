@echo off
title ORA ComfyUI Launcher
echo [ORA] Launching ComfyUI for Image Generation...

:: Use the proven command from start_vllm.bat
cd /d L:\ComfyUI
L:\ORADiscordBOT_Env\Scripts\python.exe main.py --listen 127.0.0.1 --port 8188 --normalvram --disable-cuda-malloc --enable-cors-header * --force-fp16

pause
