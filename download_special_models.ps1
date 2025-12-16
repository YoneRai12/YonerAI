$ErrorActionPreference = "Stop"

Write-Host "==========================================="
Write-Host "⬇️ DOWNLOADING Specialized Models"
Write-Host "==========================================="
Write-Host "1. T5Gemma-TTS-2b-2b (Aratako)"
Write-Host "2. SAM 3 (facebook/sam3)"
Write-Host "   (If SAM3 fails, please verify repo name)"
Write-Host "==========================================="

set "HF_HOME=L:\ai_models\huggingface"
set "HUGGINGFACE_HUB_CACHE=L:\ai_models\huggingface\hub"

# 1. T5Gemma-TTS
Write-Host "`nDownloading T5Gemma-TTS-2b-2b..."
huggingface-cli download Aratako/T5Gemma-TTS-2b-2b --local-dir "L:\ai_models\huggingface\Aratako_T5Gemma-TTS-2b-2b"

# 2. SAM 3
Write-Host "`nDownloading SAM 3..."
try {
    huggingface-cli download facebook/sam3 --local-dir "L:\ai_models\huggingface\facebook_sam3"
}
catch {
    Write-Host "⚠️ SAM 3 download failed. Trying SAM 2 (hiera-large) fallback..."
    huggingface-cli download facebook/sam2-hiera-large --local-dir "L:\ai_models\huggingface\facebook_sam2_hiera_large"
}

Write-Host "`n✅ Downloads Complete."
Write-Host "==========================================="
pause
