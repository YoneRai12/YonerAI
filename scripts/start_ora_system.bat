@echo off
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%.."
set "ROOT_DIR=%CD%"
chcp 65001 >nul
title ORA Ecosystem Unified Launcher

echo ========================================================
echo 🚀 ORA System 全システム統合起動
echo 📂 ROOT: %ROOT_DIR%
echo ========================================================

:: --- [CLEANUP] ---
echo [0/9] プロセスとポートの競合を解消中...
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM uvicorn.exe >nul 2>&1
taskkill /F /IM node.exe >nul 2>&1
taskkill /F /IM ngrok.exe >nul 2>&1
echo ✅ クリーンアップ完了

:: --- [START SERVICES] ---

:: 1. Core API (New)
echo [1/9] ORA Core API (Port 8001) を起動中...
:: Note: Using specific system python found in environment check
start "ORA-CoreAPI" cmd /k "cd /d "%ROOT_DIR%\core\src" && C:\Users\YoneRai12\AppData\Local\Programs\Python\Python311\python.exe -m uvicorn ora_core.main:app --reload --host 127.0.0.1 --port 8001"
echo ✅ Step 1 OK

:: 2. Web Client (New)
echo [2/9] ORA Web Client (Port 3000) を起動中...
start "ORA-WebClient" cmd /k "cd /d "%ROOT_DIR%\clients\web" && npm run dev"
echo ✅ Step 2 OK

:: 3. Ngrok (Optional)
echo [3/9] Ngrok トンネルを起動中...
start "ORA-Ngrok" cmd /k "cd /d "%ROOT_DIR%" && ngrok http --host-header=rewrite 3000"
echo ✅ Step 3 OK

:: 4. Legacy Web API (Port 8000 - for Bot compatibility)
echo [4/9] Legacy API (Port 8000) を起動中...
start "ORA-WebAPI-Legacy" cmd /k "cd /d "%ROOT_DIR%" && set PYTHONPATH=. && L:\ORADiscordBOT_Env\Scripts\uvicorn.exe src.web.app:app --reload --host 0.0.0.0 --port 8000"
echo ✅ Step 4 OK

:: 5. ComfyUI
echo [5/9] ComfyUI (FLUX) をチェック中...
if exist "L:\ComfyUI\main.py" (
    echo    >> L:ドメインのComfyUIを起動します
    start "ORA-ComfyUI" cmd /k "cd /d L:\ComfyUI && L:\ORADiscordBOT_Env\Scripts\python.exe main.py --listen 127.0.0.1 --port 8188 --normalvram"
) else (
    echo    -- 見つかりませんでした（スキップ）
)
echo ✅ Step 5 OK

:: 6. Voice
echo [6/9] 音声合成エンジンを起動中...
start "ORA-Engine-Voice" cmd /k "cd /d "%ROOT_DIR%" && L:\ORADiscordBOT_Env\Scripts\python.exe src\services\voice_server.py"
echo ✅ Step 6 OK

:: 7. Layer
echo [7/9] 思考レイヤーエンジンを起動中...
start "ORA-Engine-Layer" cmd /k "cd /d "%ROOT_DIR%" && L:\ORADiscordBOT_Env\Scripts\python.exe src\services\layer_server.py"
echo ✅ Step 7 OK

:: 8. Visual
echo [8/9] 画像解析（Vision）エンジンを起動中...
start "ORA-Engine-Visual" cmd /k "cd /d "%ROOT_DIR%" && L:\ORADiscordBOT_Env\Scripts\python.exe src\services\visual_server.py"
echo ✅ Step 8 OK

:: 9. Bot & Worker
echo [9/9] Bot コアプロセスを起動中...
start "ORA-Core-Bot" cmd /k "cd /d "%ROOT_DIR%" && scripts\run_bot_loop.bat"
start "ORA-Worker-Bot" cmd /k "cd /d "%ROOT_DIR%" && scripts\run_worker_loop.bat"
echo ✅ 全ての命令が送信されました！

:: --- [FINALIZE] ---
echo.
echo ========================================================
echo ✅ 起動シーケンス完了！
echo Core API: http://localhost:8001/docs
echo Web Client: http://localhost:3000
echo ========================================================
:: Wait a bit for servers to startup then open browser
timeout /t 5 >nul
start http://localhost:3000
pause
