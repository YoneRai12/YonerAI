@echo off
echo Downloading Stable Diffusion 3.5 Large...
echo This is a large file (10GB+), please wait.
echo Destination: L:\AI_Models\Stable-diffusion\sd3.5_large.safetensors

cd /d "L:\AI_Models\Stable-diffusion"
curl -L -O "https://huggingface.co/stabilityai/stable-diffusion-3.5-large/resolve/main/sd3.5_large.safetensors"

if %errorlevel% neq 0 (
    echo Download Failed!
    pause
    exit /b %errorlevel%
)

echo Download Complete!
pause
