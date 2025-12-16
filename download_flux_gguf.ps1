$modelUrl = "https://huggingface.co/city96/FLUX.1-dev-gguf/resolve/main/flux1-dev-Q8_0.gguf"
$destPath = "L:\ComfyUI\models\unet\flux1-dev-Q8_0.gguf"

Write-Host "Downloading Flux 1 Dev Q8_0 GGUF (approx 12.8GB)..."
Invoke-WebRequest -Uri $modelUrl -OutFile $destPath -UserAgent "NativeHost"
Write-Host "Download Complete."
