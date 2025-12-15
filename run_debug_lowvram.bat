@echo off
chcp 65001 > nul
echo ===========================================
echo 🛠️ COMFYUI LOW VRAM DEBUGGER
echo ===========================================
echo.
echo Running ComfyUI with --lowvram and --disable-cuda-malloc...
echo This attempts to fix the "Silent Crash" during Model Loading.
echo.

cd /d L:\ComfyUI
L:\ORADiscordBOT_Env\Scripts\python.exe main.py --listen 127.0.0.1 --port 8188 --lowvram --disable-cuda-malloc

echo.
echo ===========================================
echo ❌ COMFYUI HAS EXITED.
echo ===========================================
pause
