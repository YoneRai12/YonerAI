# yonerai.com/install command page

Status: public content contract for the future `https://yonerai.com/install`
page. This repository does not deploy the site and does not include production
installer secrets.

## Page purpose

Show users the one-command YonerAI CLI Local Runtime install path. `yonerai.com`
is only the guide page. It must not be an installer file source.

## Hero

Install YonerAI.

Latest stable: `v0.7.0`.

The install source of truth is GitHub Releases. `yonerai.com` must not host
installer scripts, release manifests, ZIP artifacts, or SHA256 sidecars unless
a future signed hosting lane explicitly approves it.

## Primary copy

YonerAI CLI Local Runtime v0.7.0 can be installed with a quick command or with
a verified command that checks `install.ps1.sha256` before execution. This is
stable for the local CLI runtime slice. It is not full YonerAI cloud production
and not a production-signed installer.

## Quick install

```powershell
irm https://install.yonerai.com | iex
```

What this does:

- downloads a static Cloudflare wrapper from `install.yonerai.com`
- the wrapper downloads `install.ps1` and `install.ps1.sha256` from the latest
  stable GitHub Release asset redirect
- verifies `install.ps1` against the sidecar SHA256 before execution
- downloads the versioned release manifest from GitHub Release assets
- downloads the versioned YonerAI ZIP from GitHub Release assets
- verifies the ZIP SHA256 from the manifest before extraction
- runs `install-local.ps1` only after it is found inside the verified archive

What this does not do:

- does not fetch ZIPs, manifests, or sidecar hashes from `yonerai.com`
- does not accept local/custom manifest or artifact paths
- does not mutate PATH by default
- does not edit the registry
- does not install services
- does not request admin rights
- does not store provider keys
- does not enable production cloud runtime, live integrations, or production
  account login
- does not include production signing keys or a production trust store

GitHub Release fallback:

```powershell
iex "& { $(irm https://github.com/YoneRai12/YonerAI/releases/latest/download/install.ps1) } -Execute -Launch"
```

## Verified install

Use this when you want to verify the bootstrap script before execution. It
downloads `install.ps1` and `install.ps1.sha256` from GitHub Releases, checks
the SHA256 sidecar, and fails closed before execution if the sidecar is missing,
malformed, or mismatched.

```powershell
$ErrorActionPreference = "Stop"
$base = "https://github.com/YoneRai12/YonerAI/releases/latest/download"
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("yonerai-bootstrap-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmp | Out-Null
try {
  $script = Join-Path $tmp "install.ps1"
  $sidecar = Join-Path $tmp "install.ps1.sha256"
  irm "$base/install.ps1" -OutFile $script
  irm "$base/install.ps1.sha256" -OutFile $sidecar
  $expected = ((Get-Content -LiteralPath $sidecar -Raw) -split '\s+')[0].ToLowerInvariant()
  if ($expected -notmatch "^[a-f0-9]{64}$") { throw "install.ps1 sidecar SHA256 is invalid" }
  $actual = (Get-FileHash -LiteralPath $script -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actual -ne $expected) { throw "install.ps1 hash mismatch" }
  $scriptText = Get-Content -LiteralPath $script -Raw
  if ($scriptText -notmatch "Invoke-VerifiedLocalBootstrap" -or $scriptText -match "install.ps1 is still plan-only") {
    throw "install.ps1 is not an executable bootstrap. Refusing to launch."
  }
  & powershell -NoProfile -ExecutionPolicy Bypass -File $script -Execute -Launch
} finally {
  if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Recurse -Force }
}
```

日本語で言うと、この verified command は GitHub Release から取得した
`install.ps1` が sidecar の SHA256 と一致した場合だけ実行します。hash が
一致しない場合はその場で止まり、インストール処理へ進みません。

## Safe manual install

```powershell
# 1. Download YonerAI-0.7.0.zip from the GitHub Release.
# 2. Extract the ZIP.
cd "$HOME\Downloads\YonerAI-0.7.0"
python --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -r core/requirements.txt httpx
python -m pip install -e clients/cli
yonerai
```

Use Python 3.11 or newer. If `yonerai` is not found, activate the virtual
environment again with `.\.venv\Scripts\Activate.ps1`.

## Local bootstrap helper

Archives or checkouts that include `install-local.ps1` can use the plan-first
local bootstrap helper:

```powershell
# Show the local install plan only.
.\install-local.ps1

# Explicitly create .venv, install the local CLI package, and launch YonerAI.
.\install-local.ps1 -Execute -Launch
```

If Windows blocks local script execution, run the same helper without changing
the machine-wide execution policy:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install-local.ps1 -Execute -Launch
```

The helper does not mutate PATH, edit the registry, install services, request
admin rights, run `irm ... | iex`, or execute a remote installer. With
`-Execute`, `pip` may fetch Python dependencies unless already cached.

## Verify before planning

`manifest.v0.7.0.json` is a GitHub Release asset. Download it from the same
GitHub Release and save it beside the extracted ZIP contents before running
local verify or plan commands; release ZIPs intentionally do not embed
versioned manifests because the manifest records the ZIP hash.

```powershell
# Release ZIP flow: manifest.v0.7.0.json is a separate GitHub Release asset.
$manifest = ".\manifest.v0.7.0.json"
yonerai manifest verify $manifest --pretty
yonerai install plan --manifest $manifest --pretty
yonerai update check --manifest $manifest --pretty
yonerai update plan --manifest $manifest --pretty
```

These commands read local files and print verification or dry-run plans. They
do not download the release asset, install packages, mutate PATH, execute a
remote script, request admin privileges, write services, or connect to a
production control plane.

## Release links

- GitHub Release: https://github.com/YoneRai12/YonerAI/releases/tag/v0.7.0
- Release asset: https://github.com/YoneRai12/YonerAI/releases/download/v0.7.0/YonerAI-0.7.0.zip
- Manifest asset: https://github.com/YoneRai12/YonerAI/releases/download/v0.7.0/manifest.v0.7.0.json

## v0.11 alpha account-sync contract prerelease

v0.11.0-alpha.1 is the current prerelease path for public account sync
contracts, `/同期`, `yonerai sync ...`, and an official API fixture. Use it
only when explicitly testing the v0.11 alpha. Use v0.7.0 for the stable CLI
Local Runtime path.

```powershell
$manifest = ".\manifest.v0.11.0-alpha.1.json"
yonerai manifest verify $manifest --pretty
yonerai sync status --pretty --lang ja
yonerai sync preview --direction cloud-to-local --json
yonerai sync approve --dry-run --direction local-to-cloud --json
yonerai install plan --manifest $manifest --pretty
yonerai update check --manifest $manifest --pretty
```

The current GitHub Release bootstrap does not accept custom local manifest or
artifact paths for install execution. Use `yonerai manifest verify`,
`yonerai install plan`, `yonerai update check`, and `yonerai update plan` for
local v0.11 manifest inspection. Account sync remains contract/fixture only in
the public repo.

## v0.10 alpha public orchestration boundary prerelease

v0.10.0-alpha.1 is the previous prerelease path for Japanese-first Mission
Control status/navigation, public Google auth dry-run boundary hardening,
Quality Wall scan hardening, and the plan-only installer manifest default. Use
it only when explicitly testing the v0.10 alpha. Use v0.7.0 for the stable CLI
Local Runtime path.

```powershell
$manifest = ".\manifest.v0.10.0-alpha.1.json"
yonerai manifest verify $manifest --pretty
yonerai install plan --manifest $manifest --pretty
yonerai update check --manifest $manifest --pretty
```

The current GitHub Release bootstrap does not accept custom local manifest or
artifact paths for install execution. Use the CLI manifest/update commands
above for local v0.10 inspection.

## v0.9 alpha TUI value-completion and quality-wall prerelease

v0.9.0-alpha.1 is the previous prerelease path for Japanese-first TUI value
completion, stronger public Quality Wall checks, and the plan-only installer
manifest default. Use it only when explicitly testing the v0.9 alpha. Use
v0.11.0-alpha.1 for the current prerelease path or v0.7.0 for the stable CLI
Local Runtime path.

```powershell
$manifest = ".\manifest.v0.9.0-alpha.1.json"
yonerai manifest verify $manifest --pretty
yonerai install plan --manifest $manifest --pretty
yonerai update check --manifest $manifest --pretty
```

The current GitHub Release bootstrap does not accept custom local manifest or
artifact paths for install execution. Use the CLI manifest/update commands
above for local v0.9 inspection.

## v0.8 alpha install/auth boundary candidate

v0.8.0-alpha.1 is the next candidate boundary for the plan-first installer,
Google OAuth dry-run contract, OpenAI shared-traffic OFF policy, and
proposal-only self-evolution visibility. Until the GitHub prerelease exists,
this section is a content contract, not a live download promise and not a
production network installer.

```powershell
$manifest = ".\manifest.v0.8.0-alpha.1.json"
yonerai manifest verify $manifest --pretty
yonerai install plan --manifest $manifest --pretty
yonerai update check --manifest $manifest --pretty
```

The current GitHub Release bootstrap does not accept custom local manifest or
artifact paths for install execution. Use the CLI manifest/update commands
above for local v0.8 inspection.
OpenAI shared traffic remains OFF by default and local/private content is
excluded from any future shared-traffic policy.
Google auth remains a dry-run contract; this is not production Google login.

## Warnings

- No forced update or package-manager channel is provided.
- No production signature or production trust store is included in the public
  repo.
- No npm or winget channel is ready.
- Production cloud runtime and live integrations are not included.
- Provider API keys are never required for the safe default mock path.
