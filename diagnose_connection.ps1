$ErrorActionPreference = "SilentlyContinue"

Write-Host "============================"
Write-Host "🔍 DIAGNOSING CONNECTION"
Write-Host "============================"

# 1. HTTP Check
Write-Host "Checking http://127.0.0.1:8188/system_stats ..."
try {
    $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8188/system_stats" -TimeoutSec 3
    Write-Host "✅ ComfyUI is ALIVE." -ForegroundColor Green
}
catch {
    Write-Host "❌ ComfyUI is NOT responding via HTTP." -ForegroundColor Red
}

# 2. Port Check
Write-Host "`nChecking Port 8188..."
$lines = netstat -ano | findstr ":8188"

if ($lines) {
    Write-Host "✅ Port 8188 is LISTENING." -ForegroundColor Green
    
    # Handle single line or array
    if ($lines -is [string]) { $lines = @($lines) }
    
    foreach ($line in $lines) {
        if ($line -match "LISTENING") {
            Write-Host "  $line"
            # Parse PID (Last element)
            $parts = $line.Trim() -split "\s+"
            $pidVal = $parts[-1]
            
            Write-Host "  -> Verifying PID $pidVal..."
            tasklist /FI "PID eq $pidVal"
        }
    }
}
else {
    Write-Host "❌ Port 8188 is NOT LISTENING." -ForegroundColor Red
    Write-Host "   This means ComfyUI is not running or crashed."
}
Write-Host "`nDone."
