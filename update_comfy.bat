@echo off
title Updating ComfyUI
echo ========================================================
echo 🔄 Updating ComfyUI to latest version...
echo ========================================================
cd /d L:\ComfyUI
git reset --hard
git pull
echo.
echo ========================================================
echo ✅ Update Complete!
echo ========================================================
pause
