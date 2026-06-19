# YonerAI Cloudflare install wrapper

This Worker is the short one-command installer wrapper for:

```powershell
irm https://install.yonerai.com | iex
```

The Worker returns a static PowerShell wrapper. The wrapper:

- downloads `install.ps1` and `install.ps1.sha256` from the currently embedded
  trusted stable GitHub Release tag
- verifies the sidecar against the embedded trusted SHA256
- verifies `install.ps1` with SHA256 before execution
- fails closed if the sidecar is missing, malformed, or either hash check fails
- executes the verified bootstrap with `-Execute -Launch`

It does not serve `install.ps1`, `install.ps1.sha256`, release manifests, ZIP
artifacts, or local PC files from Cloudflare. GitHub Releases remain the
distribution source for executable installer assets and release archives.

Deploy from this folder only after confirming Cloudflare account access:

```powershell
npx.cmd wrangler whoami
npx.cmd wrangler deploy
```

The configured custom domain is `install.yonerai.com`. Do not replace this with
a Cloudflare Tunnel route to a local PC service.
