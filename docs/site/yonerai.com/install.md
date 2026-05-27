# yonerai.com/install content foundation

Status: public content contract for the future `https://yonerai.com/install`
page. This repository does not deploy the site and does not include production
installer secrets.

## Page purpose

Help users install and start the YonerAI CLI Local Runtime after the v0.6.0
release without presenting a remote-execution installer as ready.

## Primary copy

YonerAI CLI Local Runtime v0.6.0 runs locally from a downloaded release ZIP or
from a repository checkout. It is stable for the local CLI runtime slice. It is
not full YonerAI cloud production.

## Safe manual install

```powershell
# 1. Download YonerAI-0.6.0.zip from the GitHub Release.
# 2. Extract the ZIP.
cd "$HOME\Downloads\YonerAI-0.6.0"
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

`releases/manifest.v0.6.0.json` is available in a repository checkout. If
you are installing from the release ZIP, download `manifest.v0.6.0.json` from
the same GitHub Release and save it inside the extracted folder first; release
ZIPs intentionally do not embed versioned manifests because the manifest records
the ZIP hash.

```powershell
# Release ZIP flow: manifest.v0.6.0.json is a separate GitHub Release asset.
$manifest = ".\manifest.v0.6.0.json"
yonerai manifest verify $manifest --pretty
yonerai install plan --manifest $manifest --pretty
yonerai update check --manifest $manifest --pretty
yonerai update plan --manifest $manifest --pretty
```

In a repository checkout, use `$manifest = "releases\manifest.v0.6.0.json"`
instead.

These commands read local files and print verification or dry-run plans. They
do not download the release asset, install packages, mutate PATH, execute a
remote script, request admin privileges, write services, or connect to a
production control plane.

## Release links

- GitHub Release: https://github.com/YoneRai12/YonerAI/releases/tag/v0.6.0
- Release asset: https://github.com/YoneRai12/YonerAI/releases/download/v0.6.0/YonerAI-0.6.0.zip
- Manifest asset: https://github.com/YoneRai12/YonerAI/releases/download/v0.6.0/manifest.v0.6.0.json
- Manifest source in a checkout: `releases/manifest.v0.6.0.json`

## Warnings

- No `irm ... | iex` install flow is provided.
- No production signature or production trust store is included in the public
  repo.
- No npm or winget channel is ready.
- Official Managed Cloud remains external/contract-only.
- Production Oracle/control-plane runtime is not included.
- Live Discord is not restored.
- Provider API keys are never required for the safe default mock path.
