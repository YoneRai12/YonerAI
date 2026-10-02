param(
    [Parameter(Mandatory = $true)]
    [string]$ManifestPath,

    [switch]$Json,
    [switch]$DryRun = $true,
    [switch]$Execute
)

$ErrorActionPreference = "Stop"

if ($Execute) {
    throw "YonerAI alpha installer planner refuses non-dry-run execution."
}

if (-not $DryRun) {
    throw "YonerAI alpha installer planner is dry-run only."
}

if ($ManifestPath -match '^(?i)https?://') {
    throw "ManifestPath must be a local file. Remote manifests are not fetched."
}

$resolved = Resolve-Path -LiteralPath $ManifestPath
$raw = Get-Content -LiteralPath $resolved -Raw -Encoding UTF8
$manifest = $raw | ConvertFrom-Json

$plan = [ordered]@{
    schema_version = "yonerai-windows-install-plan/v0.1"
    ok = $true
    dry_run = $true
    product = $manifest.product
    version = $manifest.version
    release_tag = $manifest.release.tag
    artifact_count = @($manifest.artifacts).Count
    steps = @(
        "read local manifest file",
        "validate manifest metadata",
        "report required hashes and signatures",
        "stop before download, install, PATH mutation, or remote execution"
    )
    download_performed = $false
    remote_code_executed = $false
    install_performed = $false
    path_mutation = $false
    network_required = $false
    powershell_pipe_execution_allowed = $false
}

if ($Json) {
    $plan | ConvertTo-Json -Depth 8
} else {
    "YonerAI Windows install plan (dry-run only)"
    "Product: $($plan.product)"
    "Version: $($plan.version)"
    "Release tag: $($plan.release_tag)"
    "Artifacts: $($plan.artifact_count)"
    "Download performed: false"
    "Install performed: false"
    "PATH mutation: false"
    "Remote code executed: false"
}
