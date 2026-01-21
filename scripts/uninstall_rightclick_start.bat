@echo off
:: ORA System Right-Click Starter Uninstaller
:: Run as Administrator to remove right-click option

echo.
echo ============================================
echo  ORA Right-Click Startup Uninstaller
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

echo レジストリからメニュー項目を削除中...
reg delete "HKCR\Directory\Background\shell\StartORA" /f >nul 2>&1

echo.
echo ✅ 右クリックメニューから「🚀 ORA System 起動」を削除しました。
echo.
pause
