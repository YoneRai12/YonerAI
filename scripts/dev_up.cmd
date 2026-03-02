@echo off
setlocal
cd /d "%~dp0\.."

if not exist logs mkdir logs

start "ORA API" cmd /c scripts\dev_api.cmd
start "ORA WEB" cmd /c scripts\dev_web.cmd
start "ORA DISCORD" cmd /c scripts\dev_discord.cmd
start "ORA PROXY" cmd /c scripts\dev_proxy.cmd

echo Started local dev windows: API, WEB, DISCORD, PROXY.
exit /b 0
