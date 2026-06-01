param(
    [switch]$Plan,
    [switch]$Execute,
    [switch]$Launch,
    [ValidateSet("stable", "alpha")]
    [string]$Channel = "stable",
    [string]$Version = "",
    [string]$InstallDir = "",
    [switch]$NoPath,
    [string]$Manifest = "",
    [string]$Artifact = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 3.0

$GitHubReleaseBase = "https://github.com/YoneRai12/YonerAI/releases/download"
$GitHubLatestInstallScript = "https://github.com/YoneRai12/YonerAI/releases/latest/download/install.ps1"
$KnownReleases = @{
    stable = @{
        Version = "0.6.4"
        Tag = "v0.6.4"
        ManifestUrl = "$GitHubReleaseBase/v0.6.4/manifest.v0.6.4.json"
        ArtifactName = "YonerAI-0.6.4.zip"
    }
    alpha = @{
        Version = "0.11.0-alpha.1"
        Tag = "v0.11.0-alpha.1"
        ManifestUrl = "$GitHubReleaseBase/v0.11.0-alpha.1/manifest.v0.11.0-alpha.1.json"
        ArtifactName = "YonerAI-0.11.0-alpha.1.zip"
    }
}

function Write-YonerAI {
    param([string]$Message)
    Write-Host "[YonerAI] $Message"
}

function Get-ReleaseSpec {
    param(
        [string]$RequestedChannel,
        [string]$RequestedVersion
    )
    $spec = $KnownReleases[$RequestedChannel]
    if (-not $spec) {
        throw "Unknown channel. Use stable or alpha."
    }
    if (-not [string]::IsNullOrWhiteSpace($RequestedVersion) -and $RequestedVersion -ne $spec.Version) {
        throw "Unsupported version for channel $RequestedChannel. This installer only accepts the pinned GitHub Release version $($spec.Version)."
    }
    if (-not [string]::IsNullOrWhiteSpace($Manifest) -or -not [string]::IsNullOrWhiteSpace($Artifact)) {
        throw "Local or custom manifest/artifact inputs are not accepted by install.ps1. Use the pinned GitHub Release assets for the selected channel."
    }
    return $spec
}

function Assert-GitHubReleaseUrl {
    param(
        [string]$Url,
        [string]$Tag,
        [string]$Label
    )
    $prefix = "$GitHubReleaseBase/$Tag/"
    if (-not $Url.StartsWith($prefix, [System.StringComparison]::Ordinal)) {
        throw "$Label must be a pinned YoneRai12/YonerAI GitHub Release asset URL."
    }
}

function Assert-VersionedArtifactName {
    param(
        [string]$ArtifactName,
        [hashtable]$Spec
    )
    if ($ArtifactName -ne $Spec.ArtifactName) {
        throw "Artifact filename must be the pinned versioned asset $($Spec.ArtifactName)."
    }
    if ($ArtifactName -match "(?i)(latest|main|source)\.zip$") {
        throw "Artifact filename must not use latest, main, or source aliases."
    }
}

function Get-DefaultInstallDir {
    param(
        [string]$RequestedChannel,
        [string]$RequestedVersion
    )
    if (-not [string]::IsNullOrWhiteSpace($InstallDir)) {
        return [System.IO.Path]::GetFullPath($InstallDir)
    }
    $base = $env:LOCALAPPDATA
    if ([string]::IsNullOrWhiteSpace($base)) {
        $base = Join-Path $HOME "AppData\Local"
    }
    return Join-Path $base "YonerAI\cli\$RequestedChannel\$RequestedVersion"
}

function Get-DisplayInstallDir {
    param(
        [string]$RequestedChannel,
        [string]$RequestedVersion
    )
    if (-not [string]::IsNullOrWhiteSpace($InstallDir)) {
        return "<custom install dir>"
    }
    return "%LOCALAPPDATA%\YonerAI\cli\$RequestedChannel\$RequestedVersion"
}

function Invoke-GitHubDownload {
    param(
        [string]$Url,
        [string]$OutFile,
        [string]$Label
    )
    Write-YonerAI "Downloading $Label from GitHub Release"
    try {
        Invoke-WebRequest -Uri $Url -OutFile $OutFile -UseBasicParsing
    }
    catch {
        throw "Failed to download $Label from GitHub Release."
    }
}

function Assert-FileSha256 {
    param(
        [string]$Path,
        [string]$ExpectedSha256,
        [string]$Label
    )
    if ($ExpectedSha256 -notmatch "^[a-f0-9]{64}$") {
        throw "$Label expected SHA256 is invalid."
    }
    $actual = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $ExpectedSha256) {
        throw "$Label SHA256 mismatch. Refusing to continue."
    }
    Write-Host "  $Label sha256 verified: true"
}

function Read-Manifest {
    param([string]$Path)
    try {
        return (Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json)
    }
    catch {
        throw "Downloaded manifest is not valid JSON."
    }
}

function Get-ManifestArtifact {
    param(
        [object]$ManifestData,
        [hashtable]$Spec
    )
    if ([string]$ManifestData.product -ne "YonerAI") {
        throw "Manifest product is invalid."
    }
    if ([string]$ManifestData.channel -ne $Channel) {
        throw "Manifest channel does not match requested channel."
    }
    if ([string]$ManifestData.version -ne $Spec.Version) {
        throw "Manifest version does not match pinned release."
    }
    if ([string]$ManifestData.release.tag -ne $Spec.Tag) {
        throw "Manifest release tag does not match pinned release."
    }
    $artifact = @($ManifestData.artifacts) | Where-Object {
        [System.IO.Path]::GetFileName([string]$_.url) -eq $Spec.ArtifactName
    } | Select-Object -First 1
    if (-not $artifact) {
        throw "Manifest does not contain the pinned GitHub artifact."
    }
    $artifactUrl = [string]$artifact.url
    $artifactName = [System.IO.Path]::GetFileName($artifactUrl)
    $artifactSha256 = [string]$artifact.sha256
    $artifactSizeBytes = [int64]$artifact.size_bytes
    $null = Assert-VersionedArtifactName -ArtifactName $artifactName -Spec $Spec
    $null = Assert-GitHubReleaseUrl -Url $artifactUrl -Tag $Spec.Tag -Label "Artifact"
    if ($artifactSha256 -notmatch "^[a-f0-9]{64}$") {
        throw "Artifact SHA256 in manifest is invalid."
    }
    if (-not ($artifact.size_bytes -is [int] -or $artifact.size_bytes -is [long])) {
        throw "Artifact size in manifest is invalid."
    }
    return [pscustomobject]@{
        id = [string]$artifact.id
        kind = [string]$artifact.kind
        target = [string]$artifact.target
        os = [string]$artifact.os
        arch = [string]$artifact.arch
        url = $artifactUrl
        sha256 = $artifactSha256
        size_bytes = $artifactSizeBytes
    }
}

function Expand-VerifiedArtifact {
    param(
        [string]$ZipPath,
        [string]$Destination
    )
    if (-not (Test-Path -LiteralPath $Destination -PathType Container)) {
        New-Item -ItemType Directory -Path $Destination | Out-Null
    }
    $extractRoot = Join-Path $Destination "source"
    if (Test-Path -LiteralPath $extractRoot) {
        throw "Install target already contains a source folder. Choose a different -InstallDir."
    }
    Expand-Archive -LiteralPath $ZipPath -DestinationPath $extractRoot
    $installLocal = Get-ChildItem -LiteralPath $extractRoot -Recurse -Filter "install-local.ps1" -File |
        Where-Object {
            Test-Path -LiteralPath (Join-Path $_.DirectoryName "clients\cli\pyproject.toml") -PathType Leaf
        } |
        Select-Object -First 1
    if (-not $installLocal) {
        throw "Verified GitHub artifact does not contain install-local.ps1 in a complete YonerAI source tree."
    }
    return $installLocal.FullName
}

function Invoke-VerifiedLocalBootstrap {
    param([string]$InstallLocalPath)
    $args = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $InstallLocalPath, "-Execute")
    if ($Launch) {
        $args += "-Launch"
    }
    Write-YonerAI "Running verified artifact bootstrap"
    & powershell @args
    if ($LASTEXITCODE -ne 0) {
        throw "Verified artifact bootstrap failed."
    }
}

$spec = Get-ReleaseSpec -RequestedChannel $Channel -RequestedVersion $Version
Assert-GitHubReleaseUrl -Url $spec.ManifestUrl -Tag $spec.Tag -Label "Manifest"
$targetDir = Get-DefaultInstallDir -RequestedChannel $Channel -RequestedVersion $spec.Version
$targetDisplay = Get-DisplayInstallDir -RequestedChannel $Channel -RequestedVersion $spec.Version

Write-YonerAI "GitHub Release installer"
Write-Host "  default channel: stable"
Write-Host "  selected channel: $Channel"
Write-Host "  selected version: $($spec.Version)"
Write-Host "  recommended script source: $GitHubLatestInstallScript"
Write-Host "  manifest source: $($spec.ManifestUrl)"
Write-Host "  artifact source: GitHub Release asset only"
Write-Host "  install target: $targetDisplay"
Write-Host "  production signature/trust store: not included"
Write-Host "  PATH mutation: disabled"
Write-Host "  not performed unless -Execute: download, extraction, pip install, launch"
Write-Host "  never performed: registry mutation, service install, admin request, provider key storage"

if (-not $Execute) {
    Write-Host ""
    Write-YonerAI "Plan only. Nothing was installed."
    Write-Host "Run this to install the latest stable from GitHub Release assets:"
    Write-Host "  & ([scriptblock]::Create((irm $GitHubLatestInstallScript))) -Execute -Launch"
    Write-Host "Run this only when you explicitly want the alpha channel:"
    Write-Host "  & ([scriptblock]::Create((irm $GitHubLatestInstallScript))) -Channel alpha -Execute -Launch"
    exit 0
}

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("yonerai-install-" + [System.Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tempRoot | Out-Null
try {
    $manifestPath = Join-Path $tempRoot "manifest.json"
    $artifactPath = Join-Path $tempRoot $spec.ArtifactName
    Invoke-GitHubDownload -Url $spec.ManifestUrl -OutFile $manifestPath -Label "manifest"
    $manifestData = Read-Manifest -Path $manifestPath
    $releaseArtifact = Get-ManifestArtifact -ManifestData $manifestData -Spec $spec
    Invoke-GitHubDownload -Url ([string]$releaseArtifact.url) -OutFile $artifactPath -Label "artifact"
    Assert-FileSha256 -Path $artifactPath -ExpectedSha256 ([string]$releaseArtifact.sha256) -Label "artifact"
    $actualSize = [int64](Get-Item -LiteralPath $artifactPath).Length
    if ($actualSize -ne [int64]$releaseArtifact.size_bytes) {
        throw "Artifact size mismatch. Refusing to continue."
    }
    Write-Host "  artifact size verified: true"
    $installLocal = Expand-VerifiedArtifact -ZipPath $artifactPath -Destination $targetDir
    Invoke-VerifiedLocalBootstrap -InstallLocalPath $installLocal
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}

Write-Host ""
Write-YonerAI "Install flow completed from verified GitHub Release assets."
