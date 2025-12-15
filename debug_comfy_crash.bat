@echo off
chcp 65001 > nul
echo ===========================================
echo 🛠️ COMFYUI CRASH DEBUGGER
echo ===========================================

set "COMFY_DIR=L:\ComfyUI"
set "NODE_FILE=%COMFY_DIR%\custom_nodes\websocket_image_save.py"

echo.
echo [1] Disabling websocket_image_save.py...
if exist "%NODE_FILE%" (
    ren "%NODE_FILE%" "websocket_image_save.py.bak"
    echo    ✅ Disabled (Renamed to .bak)
) else (
    echo    ℹ️ File not found or already disabled (Skipping).
)

echo.
echo [2] Launching ComfyUI Manually...
echo    Command: python main.py --listen 127.0.0.1 --port 8188
echo.
echo    ⚠️  もしクラッシュした場合、ここにエラーが出ます。
echo    ⚠️  最後の20行をコピーして教えてください。
echo.

cd /d "%COMFY_DIR%"
L:\ORADiscordBOT_Env\Scripts\python.exe main.py --listen 127.0.0.1 --port 8188

echo.
echo ===========================================
echo ❌ COMFYUI HAS EXITED (CRASHED).
echo ===========================================
pause
