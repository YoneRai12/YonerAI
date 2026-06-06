param(
    [switch]$Plan,
    [switch]$Execute,
    [switch]$Launch,
    [ValidateSet("stable", "alpha")]
    [string]$Channel = "stable",
    [string]$Version = "",
    [string]$InstallDir = "",
    [switch]$Repair,
    [switch]$Force,
    [switch]$CleanRetry,
    [switch]$SetPath,
    [switch]$NoPath,
    [string]$Manifest = "",
    [string]$Artifact = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 3.0

$GitHubApiBase = "https://api.github.com/repos/YoneRai12/YonerAI/releases"
$GitHubReleaseBase = "https://github.com/YoneRai12/YonerAI/releases/download"
$GitHubLatestInstallScript = "https://github.com/YoneRai12/YonerAI/releases/latest/download/install.ps1"

function Write-YonerAI {
    param([string]$Message)
    Write-Host "[YonerAI] $Message"
}

function Get-CurrentPowerShellPath {
    $path = (Get-Process -Id $PID).Path
    if ([string]::IsNullOrWhiteSpace($path)) {
        return "powershell"
    }
    return $path
}

function Invoke-GitHubApi {
    param(
        [string]$Url,
        [string]$Label
    )
    try {
        return Invoke-RestMethod -Uri $Url -Headers @{
            Accept = "application/vnd.github+json"
            "User-Agent" = "YonerAI-installer"
        }
    }
    catch {
        throw "Failed to read $Label from GitHub Releases."
    }
}

function Get-ReleaseFromApi {
    param(
        [string]$RequestedChannel,
        [string]$RequestedVersion
    )

    if (-not [string]::IsNullOrWhiteSpace($RequestedVersion)) {
        $tag = "v$RequestedVersion"
        $release = Invoke-GitHubApi -Url "$GitHubApiBase/tags/$tag" -Label "release $tag"
        if ($RequestedChannel -eq "stable" -and [bool]$release.prerelease) {
            throw "Requested stable version is a prerelease. Use -Channel alpha."
        }
        if ($RequestedChannel -eq "alpha" -and -not [bool]$release.prerelease) {
            throw "Requested alpha version is not a prerelease. Use -Channel stable."
        }
        return $release
    }

    if ($RequestedChannel -eq "stable") {
        $release = Invoke-GitHubApi -Url "$GitHubApiBase/latest" -Label "latest stable release"
        if ([bool]$release.prerelease) {
            throw "GitHub latest release unexpectedly points to a prerelease."
        }
        return $release
    }

    $releases = @(Invoke-GitHubApi -Url "$GitHubApiBase?per_page=30" -Label "latest prereleases")
    $candidate = $releases |
        Where-Object {
            [bool]$_.prerelease -and
            -not [bool]$_.draft -and
            ([string]$_.tag_name -match "^v[0-9]+\.[0-9]+\.[0-9]+-alpha\.[0-9]+$")
        } |
        Select-Object -First 1
    if (-not $candidate) {
        throw "No alpha prerelease with release assets was found."
    }
    return $candidate
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

function Get-AssetUrl {
    param(
        [object]$Release,
        [string]$AssetName
    )
    $asset = @($Release.assets) |
        Where-Object { [string]$_.name -eq $AssetName } |
        Select-Object -First 1
    if (-not $asset) {
        throw "GitHub Release is missing required asset $AssetName."
    }
    $url = [string]$asset.browser_download_url
    Assert-GitHubReleaseUrl -Url $url -Tag ([string]$Release.tag_name) -Label $AssetName
    return $url
}

function Get-ReleaseSpec {
    param(
        [string]$RequestedChannel,
        [string]$RequestedVersion
    )
    if (-not [string]::IsNullOrWhiteSpace($Manifest) -or -not [string]::IsNullOrWhiteSpace($Artifact)) {
        throw "Custom manifest/artifact inputs are not accepted by install.ps1. Use GitHub Release assets for install, or use 'yonerai install plan' for local dry-run planning."
    }

    $release = Get-ReleaseFromApi -RequestedChannel $RequestedChannel -RequestedVersion $RequestedVersion
    $tag = [string]$release.tag_name
    if ($tag -notmatch "^v(?<version>[0-9]+\.[0-9]+\.[0-9]+(?:-(?:alpha|beta|rc)\.[0-9]+)?)$") {
        throw "GitHub Release tag is not a supported YonerAI version."
    }
    $releaseVersion = $Matches.version
    $manifestName = "manifest.$tag.json"
    $artifactName = "YonerAI-$releaseVersion.zip"

    return @{
        Version = $releaseVersion
        Tag = $tag
        ManifestName = $manifestName
        ManifestUrl = Get-AssetUrl -Release $release -AssetName $manifestName
        ArtifactName = $artifactName
    }
}

function Assert-VersionedArtifactName {
    param(
        [string]$ArtifactName,
        [hashtable]$Spec
    )
    if ($ArtifactName -ne $Spec.ArtifactName) {
        throw "Artifact filename must be the selected versioned asset $($Spec.ArtifactName)."
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

function Get-DisplayBinDir {
    $base = $env:LOCALAPPDATA
    if ([string]::IsNullOrWhiteSpace($base)) {
        return "%LOCALAPPDATA%\YonerAI\bin"
    }
    return "%LOCALAPPDATA%\YonerAI\bin"
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
        throw "Manifest version does not match the selected release."
    }
    if ([string]$ManifestData.release.tag -ne $Spec.Tag) {
        throw "Manifest release tag does not match the selected release."
    }
    $artifact = @($ManifestData.artifacts) | Where-Object {
        [System.IO.Path]::GetFileName([string]$_.url) -eq $Spec.ArtifactName
    } | Select-Object -First 1
    if (-not $artifact) {
        throw "Manifest does not contain the selected GitHub artifact."
    }
    $artifactUrl = [string]$artifact.url
    $artifactName = [System.IO.Path]::GetFileName($artifactUrl)
    $artifactSha256 = [string]$artifact.sha256
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
        size_bytes = [int64]$artifact.size_bytes
    }
}

function Get-InstallTargetState {
    param([string]$Destination)
    if (-not (Test-Path -LiteralPath $Destination -PathType Container)) {
        return [pscustomobject]@{ Exists = $false; Kind = "missing"; Message = "missing" }
    }
    $source = Join-Path $Destination "source"
    $venv = Join-Path $source ".venv"
    $exe = Join-Path $venv "Scripts\yonerai.exe"
    if (Test-Path -LiteralPath $exe -PathType Leaf) {
        return [pscustomobject]@{ Exists = $true; Kind = "installed"; Message = "already installed same version or previous attempt" }
    }
    if (Test-Path -LiteralPath $source -PathType Container) {
        return [pscustomobject]@{ Exists = $true; Kind = "partial_source"; Message = "partial source folder exists" }
    }
    if (Test-Path -LiteralPath $venv -PathType Container) {
        return [pscustomobject]@{ Exists = $true; Kind = "partial_venv"; Message = "partial virtual environment exists" }
    }
    $children = @(Get-ChildItem -LiteralPath $Destination -Force -ErrorAction SilentlyContinue)
    if ($children.Count -gt 0) {
        return [pscustomobject]@{ Exists = $true; Kind = "nonempty"; Message = "install target is not empty" }
    }
    return [pscustomobject]@{ Exists = $true; Kind = "empty"; Message = "empty" }
}

function Backup-ExistingInstallTarget {
    param([string]$Destination)
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backup = "$Destination.backup-$stamp"
    if (Test-Path -LiteralPath $backup) {
        $backup = "$Destination.backup-$stamp-$([System.Guid]::NewGuid().ToString('N').Substring(0, 8))"
    }
    Move-Item -LiteralPath $Destination -Destination $backup
    Write-Host "  previous install target moved to backup: <install-dir>.backup-$stamp"
}

function Test-ReinstallRequested {
    return [bool]($Repair -or $Force -or $CleanRetry)
}

function Assert-InstallTargetDoesNotBlockDownload {
    param([string]$Destination)
    $state = Get-InstallTargetState -Destination $Destination
    if (-not $state.Exists -or $state.Kind -eq "empty") {
        return
    }
    if (Test-ReinstallRequested) {
        Write-Host "  reinstall mode: requested"
        Write-Host "  existing target state: $($state.Kind)"
        return
    }
    throw "Install target already contains a YonerAI runtime or partial install ($($state.Kind)). Re-run with -Repair, -Force, or -CleanRetry to move the old target aside, or choose a different -InstallDir."
}

function Prepare-InstallTarget {
    param([string]$Destination)
    $state = Get-InstallTargetState -Destination $Destination
    if (-not $state.Exists) {
        return
    }
    if ($state.Kind -eq "empty") {
        return
    }
    if (Test-ReinstallRequested) {
        if ($Force) {
            Write-Host "  force reinstall: true"
        }
        if ($CleanRetry) {
            Write-Host "  clean retry: true"
        }
        Backup-ExistingInstallTarget -Destination $Destination
        return
    }
    throw "Install target already contains a YonerAI runtime or partial install ($($state.Kind)). Re-run with -Repair, -Force, or -CleanRetry to move the old target aside, or choose a different -InstallDir."
}

function Get-CommandKind {
    param(
        [string]$Source,
        [string]$ExpectedBin,
        [string]$ExpectedInstall
    )
    if ([string]::IsNullOrWhiteSpace($Source)) {
        return "unknown"
    }
    $normalized = $Source.Trim()
    if (-not [string]::IsNullOrWhiteSpace($ExpectedBin) -and $normalized.StartsWith($ExpectedBin, [System.StringComparison]::OrdinalIgnoreCase)) {
        return "expected user PATH wrapper"
    }
    if (-not [string]::IsNullOrWhiteSpace($ExpectedInstall) -and $normalized.StartsWith($ExpectedInstall, [System.StringComparison]::OrdinalIgnoreCase)) {
        return "expected installed runtime"
    }
    if ($normalized -match "(?i)\\Python[^\\]*\\Scripts\\yonerai\.exe$") {
        return "old Python Scripts executable may shadow the wrapper"
    }
    if ($normalized -match "(?i)\\Scripts\\yonerai\.exe$") {
        return "external Python Scripts executable may shadow the wrapper"
    }
    return "external PATH entry"
}

function Show-YonerAICommandDiagnostic {
    param(
        [string]$ExpectedInstall,
        [string]$ExpectedWrapperDisplay
    )
    $base = $env:LOCALAPPDATA
    $expectedBin = ""
    if (-not [string]::IsNullOrWhiteSpace($base)) {
        $expectedBin = Join-Path $base "YonerAI\bin"
    }
    $commands = @(Get-Command "yonerai" -All -ErrorAction SilentlyContinue)
    if ($commands.Count -eq 0) {
        Write-Host "  current yonerai command: not found on PATH"
    }
    else {
        $first = $commands | Select-Object -First 1
        $source = [string]$first.Source
        if ([string]::IsNullOrWhiteSpace($source)) {
            $source = [string]$first.Path
        }
        $kind = Get-CommandKind -Source $source -ExpectedBin $expectedBin -ExpectedInstall $ExpectedInstall
        Write-Host "  current yonerai command: $kind"
        if ($commands.Count -gt 1) {
            Write-Host "  additional yonerai commands on PATH: $($commands.Count - 1)"
        }
    }
    Write-Host "  expected installed executable: <install target>\source\...\.venv\Scripts\yonerai.exe"
    Write-Host "  expected user PATH wrapper: $ExpectedWrapperDisplay"
    Write-Host "  local diagnosis command: Get-Command yonerai -All"
}

function Expand-VerifiedArtifact {
    param(
        [string]$ZipPath,
        [string]$Destination
    )
    Prepare-InstallTarget -Destination $Destination
    if (-not (Test-Path -LiteralPath $Destination -PathType Container)) {
        New-Item -ItemType Directory -Path $Destination | Out-Null
    }
    $extractRoot = Join-Path $Destination "source"
    Expand-Archive -LiteralPath $ZipPath -DestinationPath $extractRoot
    $installLocal = Get-ChildItem -LiteralPath $extractRoot -Recurse -Filter "install-local.ps1" -File |
        Where-Object {
            Test-Path -LiteralPath (Join-Path $_.DirectoryName "clients\cli\pyproject.toml") -PathType Leaf
        } |
        Select-Object -First 1
    if (-not $installLocal) {
        throw "Verified GitHub artifact does not contain install-local.ps1 in a complete YonerAI source tree."
    }
    return [pscustomobject]@{
        InstallLocalPath = $installLocal.FullName
        SourceRoot = $installLocal.DirectoryName
    }
}

function Invoke-VerifiedLocalBootstrap {
    param([string]$InstallLocalPath)
    $shell = Get-CurrentPowerShellPath
    $args = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $InstallLocalPath, "-Execute")
    Write-YonerAI "Running verified artifact bootstrap"
    & $shell @args
    if ($LASTEXITCODE -ne 0) {
        throw "Verified artifact bootstrap failed."
    }
}

function Set-YonerAIUserPath {
    param([string]$YoneraiExe)
    if (-not $SetPath -or $NoPath) {
        return
    }
    if (-not (Test-Path -LiteralPath $YoneraiExe -PathType Leaf)) {
        throw "Installed yonerai.exe was not found after local bootstrap."
    }
    $base = $env:LOCALAPPDATA
    if ([string]::IsNullOrWhiteSpace($base)) {
        $base = Join-Path $HOME "AppData\Local"
    }
    $bin = Join-Path $base "YonerAI\bin"
    if (-not (Test-Path -LiteralPath $bin -PathType Container)) {
        New-Item -ItemType Directory -Path $bin | Out-Null
    }
    $cmdPath = Join-Path $bin "yonerai.cmd"
    "@echo off`r`n`"$YoneraiExe`" %*`r`n" | Set-Content -LiteralPath $cmdPath -Encoding ASCII
    $currentUserPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ([string]::IsNullOrWhiteSpace($currentUserPath)) {
        $newPath = $bin
    }
    else {
        $parts = @($currentUserPath -split ";") | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
        $alreadyPresent = $parts | Where-Object { $_.TrimEnd("\") -ieq $bin.TrimEnd("\") } | Select-Object -First 1
        if ($alreadyPresent) {
            $newPath = $currentUserPath
        }
        else {
            $newPath = "$bin;$currentUserPath"
        }
    }
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Host "  user PATH wrapper installed: %LOCALAPPDATA%\YonerAI\bin\yonerai.cmd"
    Write-Host "  open a new PowerShell window before typing: yonerai"
}

function Start-YonerAI {
    param([string]$YoneraiExe)
    if (-not $Launch) {
        return
    }
    if (-not (Test-Path -LiteralPath $YoneraiExe -PathType Leaf)) {
        throw "Installed yonerai.exe was not found after local bootstrap."
    }
    Write-Host ""
    Write-YonerAI "Starting YonerAI"
    & $YoneraiExe
}

Write-YonerAI "GitHub Release installer"
Write-Host "  default channel: stable"
Write-Host "  selected channel: $Channel"
Write-Host "  requested version: $(if ([string]::IsNullOrWhiteSpace($Version)) { 'latest' } else { $Version })"
Write-Host "  recommended script source: $GitHubLatestInstallScript"
Write-Host "  artifact source: GitHub Release assets only"
Write-Host "  production signature/trust store: not included"
Write-Host "  PATH mutation: disabled unless -SetPath"
Write-Host "  not performed unless -Execute: release lookup, download, extraction, pip install, launch"
Write-Host "  never performed: service install, admin request, provider key storage"
Write-Host "  optional user PATH wrapper: disabled unless -SetPath"

if (-not $Execute) {
    Write-Host ""
    Write-YonerAI "Plan only. Nothing was installed."
    Write-Host "Run this to install the latest stable from GitHub Release assets:"
    Write-Host "  irm https://install.yonerai.com | iex"
    Write-Host "Run this to repair a broken existing stable install:"
    Write-Host "  & ([scriptblock]::Create((irm $GitHubLatestInstallScript))) -Repair -Execute -Launch"
    Write-Host "Run this only when you explicitly want the latest alpha channel:"
    Write-Host "  & ([scriptblock]::Create((irm $GitHubLatestInstallScript))) -Channel alpha -Execute -Launch"
    Write-Host "Optional PATH wrapper:"
    Write-Host "  add -SetPath if you want a user PATH wrapper for future PowerShell windows"
    Show-YonerAICommandDiagnostic -ExpectedInstall "" -ExpectedWrapperDisplay "$(Get-DisplayBinDir)\yonerai.cmd"
    exit 0
}

if (-not [string]::IsNullOrWhiteSpace($Version)) {
    $preflightTargetDir = Get-DefaultInstallDir -RequestedChannel $Channel -RequestedVersion $Version
    $preflightTargetDisplay = Get-DisplayInstallDir -RequestedChannel $Channel -RequestedVersion $Version
    Write-Host "  install target: $preflightTargetDisplay"
    Write-Host "  repair mode: $([bool]$Repair)"
    Write-Host "  force mode: $([bool]$Force)"
    Write-Host "  clean retry mode: $([bool]$CleanRetry)"
    Assert-InstallTargetDoesNotBlockDownload -Destination $preflightTargetDir
}

$spec = Get-ReleaseSpec -RequestedChannel $Channel -RequestedVersion $Version
$targetDir = Get-DefaultInstallDir -RequestedChannel $Channel -RequestedVersion $spec.Version
$targetDisplay = Get-DisplayInstallDir -RequestedChannel $Channel -RequestedVersion $spec.Version

Write-Host "  selected version: $($spec.Version)"
Write-Host "  release tag: $($spec.Tag)"
Write-Host "  manifest source: $($spec.ManifestUrl)"
Write-Host "  install target: $targetDisplay"
Write-Host "  repair mode: $([bool]$Repair)"
Write-Host "  force mode: $([bool]$Force)"
Write-Host "  clean retry mode: $([bool]$CleanRetry)"
Show-YonerAICommandDiagnostic -ExpectedInstall $targetDir -ExpectedWrapperDisplay "$(Get-DisplayBinDir)\yonerai.cmd"

Assert-InstallTargetDoesNotBlockDownload -Destination $targetDir

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
    $expanded = Expand-VerifiedArtifact -ZipPath $artifactPath -Destination $targetDir
    Invoke-VerifiedLocalBootstrap -InstallLocalPath ([string]$expanded.InstallLocalPath)
    $yoneraiExe = Join-Path ([string]$expanded.SourceRoot) ".venv\Scripts\yonerai.exe"
    Set-YonerAIUserPath -YoneraiExe $yoneraiExe
    Show-YonerAICommandDiagnostic -ExpectedInstall $targetDir -ExpectedWrapperDisplay "$(Get-DisplayBinDir)\yonerai.cmd"
    Start-YonerAI -YoneraiExe $yoneraiExe
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}

Write-Host ""
Write-YonerAI "Install flow completed from verified GitHub Release assets."
