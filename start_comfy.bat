@echo off
title ORA ComfyUI Launcher
echo [ORA] Launching ComfyUI for Image Generation...

:: Try L Drive (Migrated)
if exist "L:\ComfyUI\run_nvidia_gpu.bat" (
    cd /d L:\ComfyUI
    call run_nvidia_gpu.bat
    exit /b
)

:: Try Desktop (Old)
if exist "..\ComfyUI_windows_portable\ComfyUI\run_nvidia_gpu.bat" (
    cd /d ..\ComfyUI_windows_portable\ComfyUI
    call run_nvidia_gpu.bat
    exit /b
)

echo [ERROR] ComfyUI run_nvidia_gpu.bat not found in L:\ComfyUI or standard paths.
echo Please edit start_comfy.bat to point to your ComfyUI folder.
pause
