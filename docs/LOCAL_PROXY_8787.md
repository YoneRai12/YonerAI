# Local Proxy Entry (127.0.0.1:8787)

This is a local-only reverse proxy entry to simplify dev operations.
It does not change Cloudflare/Tunnel or public host routing.

## Path Mapping

- `/` -> `127.0.0.1:3000` (Next Web)
- `/legacy/*` -> `127.0.0.1:8000` (Legacy Web API, prefix stripped)
- `/core/*` -> `127.0.0.1:8001` (Core API, prefix stripped)
- `/hooks/*` -> `127.0.0.1:3001` (Gateway, prefix stripped)

## Start

`scripts/dev_up.cmd` now starts `scripts/dev_proxy.cmd` as an additional window.

## Verify

```powershell
netstat -ano | findstr ":8787"

curl.exe -s -o NUL -w "root=%{http_code}`n"   http://127.0.0.1:8787/
curl.exe -s -o NUL -w "legacy=%{http_code}`n" http://127.0.0.1:8787/legacy/
curl.exe -s -o NUL -w "core=%{http_code}`n"   http://127.0.0.1:8787/core/health
curl.exe -s -o NUL -w "hooks=%{http_code}`n"  http://127.0.0.1:8787/hooks/healthz
```

