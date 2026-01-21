@echo off
cd /d "%~dp0\.."
chcp 65001 >nul
:loop
title ORA Worker Bot (自動再起動モード)
echo 🚀 ORA Worker プロセスを起動中...
set PYTHONPATH=.
L:\ORADiscordBOT_Env\Scripts\python.exe src\worker_bot.py
if %errorlevel% equ 99 (
    echo ❌ トークンが見つからないため、プログラムを終了します。
    exit /b 99
)
echo ⚠️ Workerプロセスが終了しました。5秒後に再起動します...
timeout /t 5
goto loop
