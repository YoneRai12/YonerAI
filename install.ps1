param(
    [switch]$Plan,
    [switch]$Execute,
    [switch]$Launch,
    [string]$Manifest = "releases\manifest.v0.8.0-alpha.1.json",
    [string]$Artifact = "YonerAI-0.8.0-alpha.1.zip"
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
    param([string]$ManifestPath)

    Test-RelativeInput -Value $ManifestPath -Label "Manifest"
    Write-Host "  manifest: $ManifestPath"
    if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
        Write-Host "  manifest status: not found locally; download it from the matching GitHub Release before a future verified install"
        return
    }

    $manifestJson = Get-Content -LiteralPath $ManifestPath -Raw
    $manifestData = $manifestJson | ConvertFrom-Json
    $version = [string]$manifestData.version
    $tag = [string]$manifestData.release.tag
    $signatureState = "missing"
    $artifactName = "missing"
    $sha256Valid = $false
    if ($manifestData.artifacts -and $manifestData.artifacts.Count -gt 0) {
        $artifact = $manifestData.artifacts[0]
        $artifactName = [System.IO.Path]::GetFileName([string]$artifact.url)
        $sha256Valid = ([string]$artifact.sha256) -match "^[a-f0-9]{64}$"
        if ($artifact.signature) {
            $signatureState = [string]$artifact.signature.status
        }
    }

    Write-Host "  manifest version: $version"
    Write-Host "  release tag: $tag"
    Write-Host "  artifact name: $artifactName"
    Write-Host "  sha256 format valid: $sha256Valid"
    Write-Host "  signature status: $signatureState"
    Write-Host "  production trust: not present in public repo"
}

Test-RelativeInput -Value $Artifact -Label "Artifact"

Write-YonerAI "Installer skeleton"
Write-Host "  purpose: future one-command local CLI bootstrap"
Write-Host "  default: dry-run plan only"
Write-Host "  install page: https://yonerai.com/install"
Write-Host "  release source: GitHub Release assets remain the distribution source"
Write-Host "  artifact: $Artifact"
Write-ManifestPlan -ManifestPath $Manifest
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
