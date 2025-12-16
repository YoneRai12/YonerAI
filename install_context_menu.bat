@echo off
title Install ORA Context Menu
echo Adding "Open ORA Bot" to Right-Click Menu...

set "KEY_NAME=HKCU\Software\Classes\Directory\Background\shell\ORABot"
set "CMD_PATH=c:\Users\YoneRai12\Desktop\ORADiscordBOT-main3\start_vllm.bat"

reg add "%KEY_NAME%" /ve /d "Open ORA Bot 🤖" /f
reg add "%KEY_NAME%" /v "Icon" /d "cmd.exe" /f
reg add "%KEY_NAME%\command" /ve /d "\"%CMD_PATH%\"" /f

echo.
echo ✅ Context menu added!
echo You can now right-click on your desktop/folder background and select "Open ORA Bot 🤖".
echo.
pause
