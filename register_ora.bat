@echo off
title Register ORA Bot to System
echo [ORA] Adding 'ora' command to Windows Registry...

:: Check for Admin
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Please Run as Administrator.
    pause
    exit /b
)

:: Get Current Directory
set "CURRENT_DIR=%~dp0"
:: Remove trailing backslash
set "CURRENT_DIR=%CURRENT_DIR:~0,-1%"

:: Clean up old keys (Aggressive Cleanup)
echo [ORA] Cleaning up old inputs...
reg delete "HKCR\Directory\Background\shell\ORA" /f >nul 2>&1
reg delete "HKCR\Directory\Background\shell\ORABot" /f >nul 2>&1
reg delete "HKCR\Directory\Background\shell\Start ORA Bot" /f >nul 2>&1
reg delete "HKCU\Software\Classes\Directory\Background\shell\ORA" /f >nul 2>&1
reg delete "HKCU\Software\Classes\Directory\Background\shell\ORABot" /f >nul 2>&1

:: Register Context Menu (Right Click on Desktop/Background)
:: Using HKCR (System-wide)
reg add "HKCR\Directory\Background\shell\ORA" /ve /d "Start ORA Bot" /f
reg add "HKCR\Directory\Background\shell\ORA" /v "Icon" /d "%SystemRoot%\System32\cmd.exe" /f
reg add "HKCR\Directory\Background\shell\ORA\command" /ve /d "\"%CURRENT_DIR%\run_l.bat\"" /f

echo.
echo [SUCCESS] Cleaned up 'ORABot' and 'ORA' keys.
echo Registered single 'Start ORA Bot' entry.
echo.
pause
