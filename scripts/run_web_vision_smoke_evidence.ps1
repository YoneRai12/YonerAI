param(
    [string]$ApiBaseUrl = "http://127.0.0.1:8000",
    [string]$ArtifactsRoot = "artifacts/ops_memory_sync",
    [string]$AdminToken = ""
)

$ErrorActionPreference = "Stop"

function Write-JsonFile {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)]$Object
    )
    $Object | ConvertTo-Json -Depth 32 | Out-File -FilePath $Path -Encoding utf8
}

function Redact-Text {
    param([string]$Text)
    if ([string]::IsNullOrWhiteSpace($Text)) {
        return $Text
    }

    $out = $Text
    $patterns = @(
        '(?i)(authorization\s*[:=]\s*)(bearer\s+)?[^\s",;]+',
        '(?i)(cookie\s*[:=]\s*)[^\r\n]+',
        '(?i)((?:x-[a-z0-9-]*token|token|api[-_]?key)\s*[:=]\s*)[^\s",;]+',
        '(?i)([?&](?:token|access_token|refresh_token|api_key|key)=)[^&\s]+',
        '(?i)("(?:authorization|cookie|token|access_token|refresh_token|api_key|key)"\s*:\s*")[^"]*(")'
    )
    foreach ($p in $patterns) {
        $out = [regex]::Replace($out, $p, '$1[REDACTED]$2')
    }
    return $out
}

function Redact-Headers {
    param([hashtable]$Headers)
    $safe = @{}
    foreach ($k in $Headers.Keys) {
        $v = [string]$Headers[$k]
        if ($k -match '(?i)(authorization|cookie|token|api[-_]?key)') {
            $safe[$k] = "[REDACTED]"
        } else {
            $safe[$k] = Redact-Text $v
        }
    }
    return $safe
}

function To-SafeString {
    param($Value)
    if ($null -eq $Value) {
        return $null
    }
    if ($Value -is [string]) {
        return Redact-Text $Value
    }
    try {
        return Redact-Text ($Value | ConvertTo-Json -Depth 32 -Compress)
    } catch {
        return Redact-Text ([string]$Value)
    }
}

function Invoke-SafeJsonGet {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [hashtable]$Headers = @{}
    )

    $safeRequest = @{
        url = Redact-Text $Url
        headers = Redact-Headers $Headers
    }

    try {
        $resp = Invoke-WebRequest -Uri $Url -Method GET -Headers $Headers -UseBasicParsing -TimeoutSec 15
        $body = $null
        if ($resp.Content) {
            try {
                $body = $resp.Content | ConvertFrom-Json -ErrorAction Stop
            } catch {
                $body = $resp.Content
            }
        }
        return @{
            ok = $true
            request = $safeRequest
            status = [int]$resp.StatusCode
            body = To-SafeString $body
        }
    } catch {
        $httpStatus = $null
        $rawBody = $null
        try {
            if ($_.Exception.Response) {
                $httpStatus = [int]$_.Exception.Response.StatusCode
                $stream = $_.Exception.Response.GetResponseStream()
                if ($stream) {
                    $reader = New-Object System.IO.StreamReader($stream)
                    $rawBody = $reader.ReadToEnd()
                    $reader.Dispose()
                }
            }
        } catch {
            $rawBody = $null
        }
        return @{
            ok = $false
            request = $safeRequest
            status = $httpStatus
            error = Redact-Text $_.Exception.Message
            body = To-SafeString $rawBody
        }
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repoRoot
try {
    $ts = Get-Date -Format "yyyyMMdd_HHmmss"
    $evidenceDir = Join-Path $repoRoot (Join-Path $ArtifactsRoot $ts)
    New-Item -ItemType Directory -Force -Path $evidenceDir | Out-Null

    $headers = @{}
    if (-not [string]::IsNullOrWhiteSpace($AdminToken)) {
        $headers["x-admin-token"] = $AdminToken
    }

    $context = @{
        collected_at = (Get-Date).ToString("o")
        api_base_url = Redact-Text $ApiBaseUrl
        has_admin_token = (-not [string]::IsNullOrWhiteSpace($AdminToken))
    }
    Write-JsonFile -Path (Join-Path $evidenceDir "00_context.json") -Object $context

    $diagUrl = "{0}/api/platform/ops/web-runtime-diagnostics" -f $ApiBaseUrl.TrimEnd("/")
    $diag = Invoke-SafeJsonGet -Url $diagUrl -Headers $headers
    Write-JsonFile -Path (Join-Path $evidenceDir "01_web-runtime-diagnostics.json") -Object $diag

    $summary = @{
        collected_at = (Get-Date).ToString("o")
        evidence_dir = $evidenceDir
        files = @(
            "00_context.json",
            "01_web-runtime-diagnostics.json"
        )
    }
    Write-JsonFile -Path (Join-Path $evidenceDir "SUMMARY.json") -Object $summary

    Write-Host "Evidence written to: $evidenceDir"
} finally {
    Pop-Location
}
