param(
    [switch]$Execute,
    [switch]$Launch,
    [string]$Python = "python",
    [string]$Venv = ".venv"
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[YonerAI] $Message"
}

function Resolve-InRepoPath {
    param(
        [string]$RepoRoot,
        [string]$RelativePath
    )
    if ([System.IO.Path]::IsPathRooted($RelativePath)) {
        throw "Refusing absolute target path. Use a path inside the extracted YonerAI folder."
    }
    $target = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $RelativePath))
    $root = [System.IO.Path]::GetFullPath($RepoRoot)
    $rootWithSeparator = $root.TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
    if ($target.Equals($root, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to use the repository root as the virtual environment target."
    }
    if (-not $target.StartsWith($rootWithSeparator, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing target path outside the extracted YonerAI folder."
    }
    return $target
}

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$CliProject = Join-Path $RepoRoot "clients\cli\pyproject.toml"
$CoreRequirements = Join-Path $RepoRoot "core\requirements.txt"

if (-not (Test-Path -LiteralPath $CliProject -PathType Leaf)) {
    throw "clients\cli\pyproject.toml was not found. Run this script from an extracted YonerAI release folder."
}
if (-not (Test-Path -LiteralPath $CoreRequirements -PathType Leaf)) {
    throw "core\requirements.txt was not found. Run this script from a complete YonerAI checkout or release archive."
}

$VenvPath = Resolve-InRepoPath -RepoRoot $RepoRoot -RelativePath $Venv
$VenvPython = Join-Path $VenvPath "Scripts\python.exe"
$YoneraiExe = Join-Path $VenvPath "Scripts\yonerai.exe"

Write-Step "Local bootstrap plan"
Write-Host "  repo: extracted YonerAI folder"
Write-Host "  venv: .\$Venv"
Write-Host "  command: create local virtual environment and install the local CLI package"
Write-Host "  package download: pip may fetch Python dependencies unless already cached"
Write-Host "  not performed: remote script execution, PATH mutation, registry change, service install, admin request"

if (-not $Execute) {
    Write-Host ""
    Write-Step "Plan only. Nothing was installed."
    Write-Host "Run this to install locally:"
    Write-Host "  .\install-local.ps1 -Execute"
    Write-Host "Run this to install and immediately start YonerAI:"
    Write-Host "  .\install-local.ps1 -Execute -Launch"
    exit 0
}

Write-Step "Checking Python"
& $Python --version

if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
    Write-Step "Creating local virtual environment"
    & $Python -m venv $VenvPath
}
else {
    Write-Step "Reusing existing local virtual environment"
}

Write-Step "Installing local CLI runtime"
& $VenvPython -m pip install -U pip
& $VenvPython -m pip install -r $CoreRequirements httpx
& $VenvPython -m pip install -e (Join-Path $RepoRoot "clients\cli")

Write-Host ""
Write-Step "Installed. To start YonerAI later:"
Write-Host "  .\$Venv\Scripts\Activate.ps1"
Write-Host "  yonerai"
Write-Host ""
Write-Step "Without activating the shell, you can also run:"
Write-Host "  .\$Venv\Scripts\yonerai.exe"

if ($Launch) {
    Write-Host ""
    Write-Step "Starting YonerAI"
    & $YoneraiExe
}
