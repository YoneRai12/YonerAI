$ErrorActionPreference = "SilentlyContinue"

Write-Host "=============================================="
Write-Host "🔍 DIAGNOSTIC REPORT: FLUX 2 CONFIGURATION"
Write-Host "=============================================="
Write-Host ""

# 1. Verify Model Files
Write-Host "[1] Checking Model Files..."
$models = @(
    "L:\ComfyUI\models\diffusion_models\flux2_dev_fp8mixed.safetensors",
    "L:\ComfyUI\models\text_encoders\mistral_3_small_flux2_fp8.safetensors",
    "L:\ComfyUI\models\vae\flux2-vae.safetensors"
)

foreach ($path in $models) {
    if (Test-Path $path) {
        Write-Host "✅ Found: $path" -ForegroundColor Green
    }
    else {
        Write-Host "❌ MISSING: $path" -ForegroundColor Red
    }
}
Write-Host ""

# 2. Find all flux_api.json files
Write-Host "[2] Searching for all flux_api.json files on L:\..."
$jsonFiles = Get-ChildItem "L:\" -Recurse -Filter "flux_api.json" -ErrorAction SilentlyContinue

if ($jsonFiles.Count -eq 0) {
    Write-Host "⚠️ No flux_api.json found on L:\ (Checking current CWD as fallback...)"
    $jsonFiles = Get-ChildItem ".\" -Recurse -Filter "flux_api.json" -ErrorAction SilentlyContinue
}

foreach ($file in $jsonFiles) {
    Write-Host "📂 Found: $($file.FullName)"
    
    # 3. Check for outdated 'type: flux'
    $content = Get-Content $file.FullName -Raw
    if ($content -match '"type"\s*:\s*"flux"') {
        Write-Host "   ⚠️  Detected outdated 'type': 'flux' (Needs 'flux2')" -ForegroundColor Yellow
        # Display context
        Select-String -Path $file.FullName -Pattern '"type"\s*:\s*"flux"' | ForEach-Object { Write-Host "      Line $($_.LineNumber): $($_.Line.Trim())" }
    }
    elseif ($content -match '"type"\s*:\s*"flux2"') {
        Write-Host "   ✅  Verified 'type': 'flux2'" -ForegroundColor Green
    }
    else {
        Write-Host "   ❓  'type' field not usually found or different format."
    }
}

Write-Host ""
Write-Host "=============================================="
Write-Host "Diagnostic Complete."
Read-Host "Press Enter to exit"
