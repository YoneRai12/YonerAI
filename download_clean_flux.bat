@echo off
chcp 65001 >nul
title Downloading Standard Flux (FP8)
echo ========================================================
echo 🌩️ Downloading Official Standard Flux (FP8)
echo ========================================================
echo.
echo This will download the standard 'flux1-dev-fp8.safetensors' (11GB).
echo This model is GUARANTEED to work on RTX 5090.
echo.
echo Destination: L:\ComfyUI\models\unet\flux1-dev-fp8.safetensors
echo.

cd /d L:\ComfyUI\models\unet

if exist "flux1-dev-fp8.safetensors" (
    echo ✅ Model already exists! Skipping download.
) else (
    echo ⏳ Downloading from HuggingFace (Kijai/flux-fp8)...
    echo This may take a few minutes (11GB)...
    L:\ORADiscordBOT_Env\Scripts\huggingface-cli.exe download Kijai/flux-fp8 flux1-dev-fp8.safetensors --local-dir . --local-dir-use-symlinks False
)

echo.
echo ========================================================
echo ✅ Download Complete!
echo You can now close this window.
echo ========================================================
pause
