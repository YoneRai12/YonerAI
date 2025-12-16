$ErrorActionPreference = "Stop"

Write-Host "==========================================="
Write-Host "⬇️ DOWNLOADING OPTIMIZED FLUX MODEL (17GB)"
Write-Host "==========================================="
Write-Host "Target: Comfy-Org/flux1-dev -> flux1-dev-fp8.safetensors"
Write-Host "Reason: Fits in 32GB VRAM (Enables Fast Mode)"

set "HF_HOME=L:\hf"
set "HUGGINGFACE_HUB_CACHE=L:\hf\hub"

# Download Standard FP8 Model (17GB)
huggingface-cli download Comfy-Org/flux1-dev flux1-dev-fp8.safetensors --local-dir "L:\ComfyUI\models\unet"

Write-Host "`n✅ Download Complete."
Write-Host "==========================================="
pause
