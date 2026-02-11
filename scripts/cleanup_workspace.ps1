param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$targets = @(
    "src\cogs\*.bak",
    "src\cogs\handlers\*.bak",
    "src\cogs\tools\*.bak",
    "core\src\server*.log",
    "test_error*.log",
    "local_mypy_report.txt",
    "mypy_report*.txt",
    "mypy_final_report.txt"
)

$files = @()
foreach ($pattern in $targets) {
    $files += Get-ChildItem -Path $pattern -File -ErrorAction SilentlyContinue
}

$files = $files | Sort-Object FullName -Unique

if (-not $files -or $files.Count -eq 0) {
    Write-Host "No cleanup targets found."
    exit 0
}

Write-Host "Cleanup targets ($($files.Count)):"
$files | ForEach-Object { Write-Host " - $($_.FullName)" }

if ($DryRun) {
    Write-Host "DryRun enabled. No files removed."
    exit 0
}

foreach ($f in $files) {
    Remove-Item -LiteralPath $f.FullName -Force -ErrorAction SilentlyContinue
}

Write-Host "Workspace cleanup completed."
