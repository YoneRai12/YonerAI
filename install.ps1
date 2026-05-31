param(
    [switch]$Plan,
    [switch]$Execute,
    [switch]$Launch,
    [string]$Manifest = "releases\manifest.v0.9.0-alpha.1.json",
    [string]$Artifact = "YonerAI-0.9.0-alpha.1.zip"
)

$ErrorActionPreference = "Stop"

function Write-YonerAI {
    param([string]$Message)
    Write-Host "[YonerAI] $Message"
}

function Test-RelativeInput {
    param(
        [string]$Value,
        [string]$Label
    )
    if ([string]::IsNullOrWhiteSpace($Value)) {
        throw "$Label must not be empty."
    }
    if ([System.IO.Path]::IsPathRooted($Value)) {
        throw "$Label must be a relative local path."
    }
    $full = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $Value))
    $root = [System.IO.Path]::GetFullPath((Get-Location).Path)
    $rootWithSeparator = $root.TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
    if (-not ($full.Equals($root, [System.StringComparison]::OrdinalIgnoreCase) -or $full.StartsWith($rootWithSeparator, [System.StringComparison]::OrdinalIgnoreCase))) {
        throw "$Label must stay inside the current YonerAI folder."
    }
}

function Write-ManifestPlan {
    param(
        [string]$ManifestPath,
        [string]$ArtifactPath
    )

    Test-RelativeInput -Value $ManifestPath -Label "Manifest"
    Test-RelativeInput -Value $ArtifactPath -Label "Artifact"
    Write-Host "  manifest: $ManifestPath"
    if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
        Write-Host "  manifest status: not found locally; download it from the matching GitHub Release before a future verified install"
        return
    }

    $manifestJson = Get-Content -LiteralPath $ManifestPath -Raw
    $manifestData = $manifestJson | ConvertFrom-Json
    $version = [string]$manifestData.version
    $tag = [string]$manifestData.release.tag
    $localArtifactName = [System.IO.Path]::GetFileName($ArtifactPath)
    $signatureState = "missing"
    $artifactName = "missing"
    $expectedSha256 = $null
    $expectedSizeBytes = $null
    $sha256Valid = $false
    $artifactNameMatches = $false
    $manifestArtifacts = @($manifestData.artifacts)
    if ($manifestArtifacts.Count -gt 0) {
        $artifact = $manifestArtifacts | Where-Object {
            [System.IO.Path]::GetFileName([string]$_.url) -eq $localArtifactName
        } | Select-Object -First 1
        if (-not $artifact) {
            $artifact = $manifestArtifacts[0]
        } else {
            $artifactNameMatches = $true
        }
        $artifactName = [System.IO.Path]::GetFileName([string]$artifact.url)
        $expectedSha256 = [string]$artifact.sha256
        $sha256Valid = $expectedSha256 -match "^[a-f0-9]{64}$"
        if ($artifact.size_bytes -is [int] -or $artifact.size_bytes -is [long]) {
            $expectedSizeBytes = [int64]$artifact.size_bytes
        }
        if ($artifact.signature) {
            $signatureState = [string]$artifact.signature.status
        }
    }

    Write-Host "  manifest version: $version"
    Write-Host "  release tag: $tag"
    Write-Host "  artifact name: $artifactName"
    Write-Host "  local artifact: $ArtifactPath"
    Write-Host "  artifact name matches manifest: $artifactNameMatches"
    Write-Host "  sha256 format valid: $sha256Valid"
    Write-Host "  signature status: $signatureState"
    Write-Host "  production trust: not present in public repo"

    if (-not $artifactNameMatches) {
        throw "Artifact filename is not present in manifest artifacts: $localArtifactName"
    }

    if (-not (Test-Path -LiteralPath $ArtifactPath -PathType Leaf)) {
        Write-Host "  local artifact status: not found; hash not checked"
        return
    }

    $actualHash = (Get-FileHash -LiteralPath $ArtifactPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $actualSizeBytes = [int64](Get-Item -LiteralPath $ArtifactPath).Length
    $hashMatches = $sha256Valid -and $actualHash -eq $expectedSha256
    $sizeMatches = $null -ne $expectedSizeBytes -and $actualSizeBytes -eq $expectedSizeBytes

    Write-Host "  local artifact sha256: $actualHash"
    Write-Host "  local artifact sha256 matches manifest: $hashMatches"
    Write-Host "  local artifact size bytes: $actualSizeBytes"
    Write-Host "  local artifact size matches manifest: $sizeMatches"

    if (-not $hashMatches) {
        throw "Artifact SHA256 mismatch. Refusing to continue even in plan mode."
    }
    if (-not $sizeMatches) {
        throw "Artifact size mismatch. Refusing to continue even in plan mode."
    }
}

Write-YonerAI "Installer skeleton"
Write-Host "  purpose: future one-command local CLI bootstrap"
Write-Host "  default: dry-run plan only"
Write-Host "  install page: https://yonerai.com/install"
Write-Host "  release source: GitHub Release assets remain the distribution source"
Write-Host "  artifact: $Artifact"
Write-ManifestPlan -ManifestPath $Manifest -ArtifactPath $Artifact
Write-Host "  planned local command after manual extraction: .\install-local.ps1 -Execute -Launch"
Write-Host "  not performed: network download, remote script execution, download-and-execute, PATH mutation, registry change, service install, admin request"

if ($Execute -or $Launch) {
    throw "install.ps1 is still plan-only. Use .\install-local.ps1 -Execute -Launch from an extracted and verified release folder for explicit local install."
}

Write-Host ""
Write-YonerAI "Plan only. Nothing was installed."
Write-Host "Next safe commands:"
Write-Host "  yonerai manifest verify $Manifest --pretty"
Write-Host "  yonerai install plan --manifest $Manifest --pretty"
Write-Host "  yonerai update check --manifest $Manifest --pretty"
Write-Host "  .\install-local.ps1"
Write-Host "  .\install-local.ps1 -Execute -Launch"
Write-Host "  yonerai update check --pretty"
