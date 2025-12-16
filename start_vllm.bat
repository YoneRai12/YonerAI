@echo off
cd /d "%~dp0"
title ORA Bot Launcher
cls
echo ===================================================
echo           ORA BOT - MODEL SELECTOR
echo ===================================================
echo.
echo Please select a mode:
echo.
echo [1] Normal / General Use (Instruct)
echo     - Model: Qwen3-VL-30B-A3B-Instruct
echo     - Best for: Chat, Tools, Long Context
echo.
echo [2] Thinking / Math Use (Reasoning)
echo     - Model: Qwen3-VL-30B-A3B-Thinking
echo     - Best for: Math, Graphs, Complex Logic
echo.
echo [3] Gaming Mode (Low Resource)
echo     - Model: Qwen2.5-VL-7B
echo     - Best for: Low Lag, Background use
echo.
echo ===================================================
echo Auto-starting Default (Instruct) in 3 seconds...
choice /c 123 /t 3 /d 1 /m "Enter choice"

if errorlevel 3 (
    set "ORA_STARTUP_MODE=gaming"
    start "ORA Gaming" powershell -NoExit -Command "& '%~dp0start_vllm_gaming.bat'"
) else if errorlevel 2 (
    set "ORA_STARTUP_MODE=thinking"
    start "ORA Thinking" powershell -NoExit -Command "& '%~dp0start_vllm_thinking.bat'"
) else if errorlevel 1 (
    set "ORA_STARTUP_MODE=instruct"
    start "ORA Instruct" powershell -NoExit -Command "& '%~dp0start_vllm_instruct.bat'"
)

echo.
echo Starting other services... (ComfyUI, Bot, API, Vision UI)
timeout /t 2 /nobreak >nul

:: Start ComfyUI
start "ComfyUI" cmd /k "cd /d L:\ComfyUI && L:\ORADiscordBOT_Env\Scripts\python.exe main.py --listen 127.0.0.1 --port 8188 --normalvram --disable-cuda-malloc --enable-cors-header * --force-fp16"

:: Start Web API
start "ORA Web API" cmd /k "L:\ORADiscordBOT_Env\Scripts\uvicorn.exe src.web.app:app --reload --port 8000"

:: Start Vision UI (Missing Component)
start "ORA Vision UI" cmd /k "cd /d %~dp0ora-ui && npm run dev"

:: Start Bot
start "ORA Bot" cmd /k "L:\ORADiscordBOT_Env\Scripts\python.exe main.py"

echo.
echo ✅ Low Orbit Ion Cannon Initialized.
exit
