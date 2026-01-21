@echo off
:: ORA System Right-Click Starter Installer
:: Run as Administrator to install right-click option

:: Get the directory of this script
set "SCRIPT_DIR=%~dp0"
set "ORA_ROOT=%SCRIPT_DIR%.."

:: Registry key for directory background context menu
set "REG_KEY=HKCR\Directory\Background\shell\StartORA"

echo.
echo ============================================
echo  ORA Right-Click Startup Installer
echo ============================================
echo.

:: Check for admin rights
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 管理者権限が必要です。
    echo    このスクリプトを右クリックして「管理者として実行」してください。
    pause
    exit /b 1
)

echo [1/3] レジストリにメニュー項目を登録中...
reg add "%REG_KEY%" /ve /d "🚀 ORA System 起動" /f
reg add "%REG_KEY%" /v "Icon" /d "cmd.exe,0" /f

echo [2/3] コマンドを登録中...
reg add "%REG_KEY%\command" /ve /d "\"%ORA_ROOT%\scripts\start_ora_system.bat\"" /f

echo [3/3] 完了！
echo.
echo ✅ 右クリックメニューに「🚀 ORA System 起動」が追加されました。
echo    デスクトップやフォルダ内で右クリック -> 「🚀 ORA System 起動」で起動できます。
echo.
pause
