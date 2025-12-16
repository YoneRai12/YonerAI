$url = "https://huggingface.co/api/models/Comfy-Org/flux2-dev/tree/main/split_files/diffusion_models"
try {
    $resp = Invoke-RestMethod -Uri $url
    $resp | Where-Object { $_.path -like "*.safetensors" } | Select-Object path, size | Format-Table -AutoSize
}
catch {
    Write-Host "Error: $_"
}
