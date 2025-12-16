$ErrorActionPreference = "Stop"

Write-Host "==========================================="
Write-Host "⬇️ CORRECTING Specialized Models Installation"
Write-Host "==========================================="
Write-Host "1. SAM 3 (Official GitHub Clone)"
Write-Host "2. T5Gemma Resources (Aratako/resources)"
Write-Host "==========================================="

set "HF_HOME=L:\ai_models\huggingface"
set "HUGGINGFACE_HUB_CACHE=L:\ai_models\huggingface\hub"

# 1. SAM 3 (Clone)
if (-not (Test-Path "L:\ai_models\github")) { New-Item -ItemType Directory -Force -Path "L:\ai_models\github" }
if (Test-Path "L:\ai_models\github\sam3") {
    Write-Host "SAM 3 repo exists. Pulling updates..."
    pushd "L:\ai_models\github\sam3"
    git pull
    popd
}
else {
    Write-Host "Cloning SAM 3..."
    git clone https://github.com/facebookresearch/sam3 "L:\ai_models\github\sam3"
}

# 2. T5Gemma Resources
Write-Host "`nDownloading T5Gemma Resources..."
huggingface-cli download Aratako/T5Gemma-TTS-2b-2b-resources --local-dir "L:\ai_models\huggingface\Aratako_T5Gemma-TTS-2b-2b-resources"

Write-Host "`n✅ Correction Complete."
Write-Host "==========================================="
pause
