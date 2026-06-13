# yonerai.com/install command page

Status: public content contract for the future `https://yonerai.com/install`
page. This repository does not deploy the site and does not include production
installer secrets.

## Page purpose

Show users the one-command YonerAI CLI Local Runtime install path. `yonerai.com`
is only the guide page. It must not be an installer file source.

## Hero

Install YonerAI.

Latest stable: `v0.8.1`.

The install source of truth is GitHub Releases. `yonerai.com` must not host
installer scripts, release manifests, ZIP artifacts, or SHA256 sidecars unless
a future signed hosting lane explicitly approves it.

## Primary copy

YonerAI CLI Local Runtime v0.8.1 can be installed with a quick command or with
a verified command that checks `install.ps1.sha256` against an embedded trusted
SHA256 before execution. This is stable for the local CLI runtime slice. It is
not full YonerAI cloud production and not a production-signed installer.

## Quick install

```powershell
irm https://install.yonerai.com | iex
```

What this does:

- downloads a static Cloudflare wrapper from `install.yonerai.com`
- the wrapper downloads `install.ps1` and `install.ps1.sha256` from the embedded
  trusted stable GitHub Release tag
- verifies the sidecar against the embedded trusted SHA256
- verifies `install.ps1` against the embedded trusted SHA256 before execution
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
- does not enable production Oracle, Official Managed Cloud, live Discord, or
  production Google login
- does not include production signing keys or a production trust store

Do not pipe `releases/latest/download/install.ps1` directly into
`Invoke-Expression`; use the short wrapper or the verified command below.

## Verified install

Use this when you want to verify the bootstrap script before execution. It
downloads `install.ps1` and `install.ps1.sha256` from the current trusted stable
GitHub Release tag, checks the SHA256 sidecar against the embedded trusted
digest, and fails closed before execution if the sidecar is missing, malformed,
not trusted, or mismatched.

```powershell
$ErrorActionPreference = "Stop"
$base = "https://github.com/YoneRai12/YonerAI/releases/download/v0.8.1"
$expected = "2ca04db3e1dc7519563e006a3d117d4cb04c7b205656fac6ea9ff7fb483cd0b8"
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("yonerai-bootstrap-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmp | Out-Null
try {
  $script = Join-Path $tmp "install.ps1"
  $sidecar = Join-Path $tmp "install.ps1.sha256"
  irm "$base/install.ps1" -OutFile $script
  irm "$base/install.ps1.sha256" -OutFile $sidecar
  $sidecarExpected = ((Get-Content -LiteralPath $sidecar -Raw) -split '\s+')[0].ToLowerInvariant()
  if ($sidecarExpected -notmatch "^[a-f0-9]{64}$") { throw "install.ps1 sidecar SHA256 is invalid" }
  if ($sidecarExpected -ne $expected) { throw "install.ps1 sidecar does not match trusted digest" }
  $actual = (Get-FileHash -LiteralPath $script -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actual -ne $expected) { throw "install.ps1 hash mismatch" }
  $scriptText = Get-Content -LiteralPath $script -Raw
  if ($scriptText -notmatch "Invoke-VerifiedLocalBootstrap" -or $scriptText -match "install.ps1 is still plan-only") {
    throw "install.ps1 is not an executable bootstrap. Refusing to launch."
  }
  & (Get-Process -Id $PID).Path -NoProfile -ExecutionPolicy Bypass -File $script -Execute -Launch
} finally {
  if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Recurse -Force }
}
```

日本語で言うと、この verified command は「GitHub Release から取得した
install.ps1 が sidecar の SHA256 と一致した場合だけ実行する」ための手順です。
hash が一致しない場合はその場で止まり、インストール処理へ進みません。

## Safe manual install

```powershell
# 1. Download YonerAI-0.8.1.zip from the GitHub Release.
# 2. Extract the ZIP.
cd "$HOME\Downloads\YonerAI-0.8.1"
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

`manifest.v0.8.1.json` is a GitHub Release asset. Download it from the same
GitHub Release and save it beside the extracted ZIP contents before running
local verify or plan commands; release ZIPs intentionally do not embed
versioned manifests because the manifest records the ZIP hash.

```powershell
# Release ZIP flow: manifest.v0.8.1.json is a separate GitHub Release asset.
$manifest = ".\manifest.v0.8.1.json"
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

- GitHub Release: https://github.com/YoneRai12/YonerAI/releases/tag/v0.8.1
- Release asset: https://github.com/YoneRai12/YonerAI/releases/download/v0.8.1/YonerAI-0.8.1.zip
- Manifest asset: https://github.com/YoneRai12/YonerAI/releases/download/v0.8.1/manifest.v0.8.1.json

## Prerelease bridge preview

v0.7.0-alpha.1 is a prerelease bridge foundation, not the stable install
recommendation. Use v0.8.1 for the current stable CLI Local Runtime unless you
are explicitly testing the official-bridge alpha.

```powershell
$manifest = ".\manifest.v0.7.0-alpha.1.json"
yonerai manifest verify $manifest --pretty
yonerai install plan --manifest $manifest --pretty
yonerai update check --manifest $manifest --pretty
yonerai update plan --manifest $manifest --pretty
```

The v0.7 prerelease path keeps the same non-actions: no download by default, no
install by default, no PATH mutation, no remote script execution, no service
install, and no production signing/trust material.

## v0.11 alpha account sync and Oracle API foundation prerelease

v0.11.0-alpha.1 is the current prerelease path for public account sync
contracts, `/同期`, `yonerai sync ...`, Official API fixture, and private
YonerAIOracle handoff alignment. Use it only when explicitly testing the v0.11
alpha. Use v0.8.1 for the stable CLI Local Runtime path.

```powershell
$manifest = ".\manifest.v0.11.0-alpha.1.json"
yonerai manifest verify $manifest --pretty
yonerai sync status --pretty --lang ja
yonerai sync preview --direction cloud-to-local --json
yonerai sync approve --dry-run --direction local-to-cloud --json
yonerai install plan --manifest $manifest --pretty
yonerai update check --manifest $manifest --pretty
.\install.ps1 -Manifest $manifest -Artifact YonerAI-0.11.0-alpha.1.zip
```

`install.ps1` stays plan-only. It may read a local v0.11 manifest and print
artifact, SHA256, signature, and trust status. It does not download, install,
mutate PATH, execute remote code, request admin, edit registry, or install
services. Account sync remains contract/fixture only in the public repo.

## v0.10 alpha public orchestration boundary prerelease

v0.10.0-alpha.1 is the previous prerelease path for Japanese-first Mission
Control status/navigation, public Google auth dry-run boundary hardening,
Quality Wall scan hardening, and the plan-only installer manifest default. Use
it only when explicitly testing the v0.10 alpha. Use v0.8.1 for the stable CLI
Local Runtime path.

```powershell
$manifest = ".\manifest.v0.10.0-alpha.1.json"
yonerai manifest verify $manifest --pretty
yonerai install plan --manifest $manifest --pretty
yonerai update check --manifest $manifest --pretty
.\install.ps1 -Manifest $manifest -Artifact YonerAI-0.10.0-alpha.1.zip
```

`install.ps1` stays plan-only. It may read a local v0.10 manifest and print
artifact, SHA256, signature, and trust status. It does not download, install,
mutate PATH, execute remote code, request admin, edit registry, or install
services.

## v0.9 alpha TUI value-completion and quality-wall prerelease

v0.9.0-alpha.1 is the previous prerelease path for Japanese-first TUI value
completion, stronger public Quality Wall checks, and the plan-only installer
manifest default. Use it only when explicitly testing the v0.9 alpha. Use
v0.11.0-alpha.1 for the current prerelease path or v0.8.1 for the stable CLI
Local Runtime path.

```powershell
$manifest = ".\manifest.v0.9.0-alpha.1.json"
yonerai manifest verify $manifest --pretty
yonerai install plan --manifest $manifest --pretty
yonerai update check --manifest $manifest --pretty
.\install.ps1 -Manifest $manifest -Artifact YonerAI-0.9.0-alpha.1.zip
```

`install.ps1` stays plan-only. It may read a local v0.9 manifest and print
artifact, SHA256, signature, and trust status. It does not download, install,
mutate PATH, execute remote code, request admin, edit registry, or install
services.

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
.\install.ps1 -Manifest $manifest -Artifact YonerAI-0.8.0-alpha.1.zip
```

`install.ps1` stays plan-only. It may read a local manifest and print artifact,
SHA256, signature, and trust status. It does not download, install, mutate
PATH, execute remote code, request admin, edit registry, or install services.
OpenAI shared traffic remains OFF by default and private/local content is
excluded from any future shared-traffic policy.
Google auth remains a dry-run contract; this is not production Google login.

## Warnings

- No `irm ... | iex` install flow is provided.
- No production signature or production trust store is included in the public
  repo.
- No npm or winget channel is ready.
- Official Managed Cloud remains external/contract-only.
- Production Oracle/control-plane runtime is not included.
- Live Discord is not restored.
- Provider API keys are never required for the safe default mock path.
