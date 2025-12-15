$ErrorActionPreference = "Stop"

Write-Host "==========================================="
Write-Host "🔄 REDOWNLOADING VAE (Validation)"
Write-Host "==========================================="

set "HF_HOME=L:\hf"
set "HUGGINGFACE_HUB_CACHE=L:\hf\hub"

Write-Host "Target: Comfy-Org/flux2-dev -> flux2-vae.safetensors"
Write-Host "Dest:   L:\ComfyUI\models\vae"

hf download Comfy-Org/flux2-dev split_files/vae/flux2-vae.safetensors --local-dir "L:\ComfyUI\models\vae" --force-download

Write-Host "`n✅ Download Complete."
Write-Host "==========================================="
Read-Host "Press Enter to exit"
