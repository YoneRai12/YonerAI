$base = "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main"
$dest = "L:\ComfyUI\models\clip"

Write-Host "Downloading CLIP-L..."
Invoke-WebRequest -Uri "$base/clip_l.safetensors" -OutFile "$dest\clip_l.safetensors" -UserAgent "NativeHost"

Write-Host "Downloading T5XXL FP8..."
Invoke-WebRequest -Uri "$base/t5xxl_fp8_e4m3fn.safetensors" -OutFile "$dest\t5xxl_fp8_e4m3fn.safetensors" -UserAgent "NativeHost"

Write-Host "CLIP models downloaded."
