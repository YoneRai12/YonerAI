@echo off
setlocal enabledelayedexpansion
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%.."
set "ROOT_DIR=%CD%"
chcp 65001 >nul
title ORA Ecosystem Unified Launcher (FINAL-ULTRA-STABLE)

echo ========================================================
echo ORA System 集中管理起動 - 高互換版
echo ROOT: %ROOT_DIR%
echo ========================================================

:: --- [CLEANUP] ---
echo [STEP 0] 以前のプロセスを終了しています...
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM uvicorn.exe >nul 2>&1
taskkill /F /IM node.exe >nul 2>&1
taskkill /F /IM cloudflared.exe >nul 2>&1
if exist "logs\cf_*.log" del /Q "logs\cf_*.log"
echo [ OK ] クリーンアップ完了
timeout /t 2 >nul

:: --- [DB INIT] ---
echo [STEP 1] データベースの準備中...
set "PYTHONPATH=%ROOT_DIR%\core\src"
python "%ROOT_DIR%\scripts\fix_user_id_column.py"
python "%ROOT_DIR%\scripts\init_core_db.py"
echo [ OK ] データベース準備完了

:: 1. ORA Core API (Brain) - Port 8001
echo [STEP 2] ORA Core API (8001) を起動中...
start "ORA-CoreAPI" cmd /k "cd /d ""%ROOT_DIR%"" && set PYTHONPATH=%ROOT_DIR%\core\src && python -m ora_core.main"
timeout /t 2 >nul

:: 2. ORA Core Web Client (New Main) - Port 3000
echo [STEP 3] ORA Web 操作画面 (3000) を起動中...
start "ORA-Web-Main" cmd /k "cd /d ""%ROOT_DIR%\clients\web"" && npm run dev"
timeout /t 2 >nul

:: 3. ORA Dashboard (Legacy) - Port 3333
echo [STEP 4] ORA ダッシュボード (3333) を起動中...
start "ORA-Dashboard-Legacy" cmd /k "cd /d ""%ROOT_DIR%\ora-ui"" && npm run dev"
timeout /t 2 >nul

:: 4. Legacy Web API - Port 8000
echo [STEP 5] レガシー API (8000) を起動中...
start "ORA-WebAPI-Legacy" cmd /k "cd /d ""%ROOT_DIR%"" && set PYTHONPATH=%ROOT_DIR% && L:\ORADiscordBOT_Env\Scripts\uvicorn.exe src.web.app:app --reload --host 0.0.0.0 --port 8000 --no-access-log"
timeout /t 2 >nul

:: --- [LOGS INIT] ---
if not exist "logs" mkdir "logs"

:: 5. External Access (Cloudflare Tunnel)
echo [STEP 6] 外部アクセストンネルを起動中...
set "CF_EXE="
if exist "%ROOT_DIR%\tools\cloudflare\cloudflared.exe" set "CF_EXE=%ROOT_DIR%\tools\cloudflare\cloudflared.exe"
if not defined CF_EXE if exist "L:\tools\cloudflare\cloudflared.exe" set "CF_EXE=L:\tools\cloudflare\cloudflared.exe"

set "CF_HELPER=%ROOT_DIR%\scripts\start_tunnel_helper.bat"

if defined CF_EXE (
    echo [ OK ] トンネルを開始: !CF_EXE!
    :: start "ORA-CF-Web" cmd /c ""%CF_HELPER%" "!CF_EXE!" http://localhost:3000 "logs\cf_web.log""
    :: start "ORA-CF-Dash" cmd /c ""%CF_HELPER%" "!CF_EXE!" http://localhost:3333 "logs\cf_dash.log""
    start "ORA-CF-API" cmd /c ""%CF_HELPER%" "!CF_EXE!" http://localhost:8001 "logs\cf_api.log""
    start "ORA-CF-Comfy" cmd /c ""%CF_HELPER%" "!CF_EXE!" http://localhost:8188 "logs\cf_comfy.log""
) else (
    echo [ERROR] cloudflared.exe が見つかりませんでした。
)
timeout /t 2 >nul

:: 6. ComfyUI (FLUX)
echo [STEP 7] ComfyUI (8188) を起動中...
if exist "L:\ComfyUI\main.py" (
    start "ORA-ComfyUI" cmd /k "cd /d L:\ComfyUI && L:\ORADiscordBOT_Env\Scripts\python.exe main.py --listen 127.0.0.1 --port 8188 --normalvram"
)

:: 7. Voice & Layer Engines
echo [STEP 8] 音声・制御エンジンを起動中...
start "ORA-Engine-Voice" cmd /k "cd /d ""%ROOT_DIR%"" && L:\ORADiscordBOT_Env\Scripts\python.exe src\services\voice_server.py"
start "ORA-Engine-Layer" cmd /k "cd /d ""%ROOT_DIR%"" && L:\ORADiscordBOT_Env\Scripts\python.exe src\services\layer_server.py"
timeout /t 1 >nul

:: 8. Visual Engine
echo [STEP 9] 視覚エンジンを起動中...
start "ORA-Engine-Visual" cmd /k "cd /d ""%ROOT_DIR%"" && L:\ORADiscordBOT_Env\Scripts\python.exe src\services\visual_server.py"
timeout /t 1 >nul

:: 9. Discord Bot
echo [STEP 10] Discord Bot を起動中...
start "ORA-Core-Bot" cmd /c ""%ROOT_DIR%\scripts\run_bot_loop.bat""
start "ORA-Worker-Bot" cmd /c ""%ROOT_DIR%\scripts\run_worker_loop.bat""
timeout /t 2 >nul

:: 10. Final Browser Open
echo [STEP 11] ローカル画面を表示しています...
timeout /t 8 >nul
:: start http://localhost:3000

echo ========================================================
echo [ OK ] 全システム起動完了！
echo 約 30-60 秒ほどで Discord に日本語で URL が届きます。
echo ========================================================
pause
