# yonerai.com/install command page

Status: public content contract for the future `https://yonerai.com/install`
page. This repository does not deploy the site and does not include production
installer secrets.

## Page purpose

Show the one-command YonerAI CLI Local Runtime install command. `yonerai.com`
is only the guide page. It must not be an installer file source.

It does not read installer bytes from `yonerai.com`. The bootstrap script,
release manifest, and ZIP artifact must come from GitHub Release assets.

## Quick install command

```powershell
& ([scriptblock]::Create((irm https://github.com/YoneRai12/YonerAI/releases/latest/download/install.ps1))) -Execute -Launch
```

What this does:

- downloads `install.ps1` from the latest stable GitHub Release asset redirect
- downloads the versioned release manifest from GitHub Release assets
- downloads the versioned YonerAI ZIP from GitHub Release assets
- verifies the ZIP SHA256 from the manifest before extraction
- runs `install-local.ps1` only after it is found inside the verified archive

What this does not do:

- does not fetch installer files, manifests, or ZIPs from `yonerai.com`
- does not accept local/custom manifest or artifact paths
- does not mutate PATH by default
- does not edit the registry
- does not install services
- does not request admin rights
- does not store provider keys
- does not enable production Oracle, Official Managed Cloud, live Discord, or
  production Google login
- does not include production signing keys or a production trust store

## Verified install command

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
  $expected = ((Get-Content -LiteralPath $sidecar -Raw).Split()[0]).ToLowerInvariant()
  if ($expected -notmatch "^[a-f0-9]{64}$") { throw "install.ps1 sidecar SHA256 is invalid" }
  $actual = (Get-FileHash -LiteralPath $script -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actual -ne $expected) { throw "install.ps1 hash mismatch" }
  & powershell -NoProfile -ExecutionPolicy Bypass -File $script -Execute -Launch
} finally {
  if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Recurse -Force }
}
```

日本語で言うと、この verified command は「GitHub Release から取得した
install.ps1 が sidecar の SHA256 と一致した場合だけ実行する」ための手順です。
hash が一致しない場合はその場で止まり、インストール処理へ進みません。

## Alpha channel

Stable is the default. Alpha requires an explicit channel flag:

```powershell
& ([scriptblock]::Create((irm https://github.com/YoneRai12/YonerAI/releases/latest/download/install.ps1))) -Channel alpha -Execute -Launch
```

## Local status commands

After install or in a checkout:

```powershell
yonerai install status --pretty
yonerai update check --channel stable --pretty
yonerai update check --channel alpha --pretty
```

These commands show source policy and dry-run update state. They do not
download or install updates.

## Source separation

`yonerai.com` is hosted separately as a Zero Trust site and must remain outside
the install trust chain. To protect the hosting PC, the site content tree must
not contain:

- `install.ps1`
- `install.ps1.sha256`
- `manifest.v*.json`
- release ZIP files

The install source of truth is GitHub Releases:

- latest stable bootstrap:
  `https://github.com/YoneRai12/YonerAI/releases/latest/download/install.ps1`
- stable release:
  `https://github.com/YoneRai12/YonerAI/releases/tag/v0.6.3`
- stable ZIP:
  `https://github.com/YoneRai12/YonerAI/releases/download/v0.6.3/YonerAI-0.6.3.zip`
- stable manifest:
  `https://github.com/YoneRai12/YonerAI/releases/download/v0.6.3/manifest.v0.6.3.json`

## Publish blocker

Do not publish the one-command install page as live-ready until the latest
stable GitHub Release contains all required assets:

- `install.ps1`
- `install.ps1.sha256`
- `manifest.v0.6.3.json`
- `YonerAI-0.6.3.zip`

## Non-claims

- This is not full YonerAI cloud production.
- This is not a production-signed installer.
- npm, winget, Microsoft Store, and production installer channels are not ready.
- Official Managed Cloud remains external/contract-only.
- Production Oracle/control-plane runtime is not included.
- Live Discord is not restored.
- Provider API keys are never required for the safe default mock path.
