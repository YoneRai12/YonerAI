@echo off
cd /d "%~dp0\.."
chcp 65001 >nul
:loop
title ORA Bot (自動再起動モード)
echo 🚀 ORA Bot メインプロセスを起動中...
set PYTHONPATH=.
L:\ORADiscordBOT_Env\Scripts\python.exe main.py
if %errorlevel% equ 99 (
    echo ❌ トークンが見つからないか設定エラーのため、プログラムを終了します。
    exit /b 99
)
echo ⚠️ Botプロセスが終了しました（クラッシュ？）。5秒後に再起動します...
timeout /t 5
goto loop
