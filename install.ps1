param(
    [switch]$Plan,
    [switch]$Execute,
    [switch]$Launch
)

$ErrorActionPreference = "Stop"

function Write-YonerAI {
    param([string]$Message)
    Write-Host "[YonerAI] $Message"
}

Write-YonerAI "Installer skeleton"
Write-Host "  purpose: future one-command local CLI bootstrap"
Write-Host "  default: dry-run plan only"
Write-Host "  install page: https://yonerai.com/install"
Write-Host "  release source: GitHub Release assets remain the distribution source"
Write-Host "  planned local command: .\install-local.ps1 -Execute -Launch"
Write-Host "  not performed: remote script execution, download-and-execute, PATH mutation, registry change, service install, admin request"

if ($Execute -or $Launch) {
    throw "install.ps1 is a dry-run skeleton. Use .\install-local.ps1 -Execute -Launch from an extracted release folder for explicit local install."
}

Write-Host ""
Write-YonerAI "Plan only. Nothing was installed."
Write-Host "Next safe commands:"
Write-Host "  .\install-local.ps1"
Write-Host "  .\install-local.ps1 -Execute -Launch"
Write-Host "  yonerai update check --pretty"
