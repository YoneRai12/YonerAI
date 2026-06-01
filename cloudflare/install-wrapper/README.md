# YonerAI Cloudflare install wrapper

This Worker is the short one-command installer wrapper for:

```powershell
irm https://install.yonerai.com | iex
```

The Worker returns a static PowerShell wrapper. The wrapper:

- downloads `install.ps1` from an immutable pinned Git commit
- verifies `install.ps1` with a SHA256 digest embedded in the Worker source
- does not trust a mutable `releases/latest` sidecar hash as the authenticity root
- fails closed if the downloaded script does not match the embedded digest
- executes only the expected plan-only bootstrap with `-Execute -Launch`

It does not serve `install.ps1`, `install.ps1.sha256`, release manifests, ZIP
artifacts, or local PC files from Cloudflare. GitHub Releases remain the
distribution source for manually downloaded release archives, but the Worker
bootstrap trust anchor is independent from mutable release assets.

Deploy from this folder only after confirming Cloudflare account access:

```powershell
npx.cmd wrangler whoami
npx.cmd wrangler deploy
```

The configured custom domain is `install.yonerai.com`. Do not replace this with
a Cloudflare Tunnel route to a local PC service.
