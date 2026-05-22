# Alpha Public Verification

Date: 2026-05-22

## Summary

`v0.1.0-alpha.1` exists as a GitHub prerelease and points at the intended
release-gate commit. The public README quickstart path was verified from a
fresh clone of the tag.

## Release State

- Tag: `v0.1.0-alpha.1`
- Tag target commit: `0808bc5cdd6d0fea7451137e70252f511bcb9cbd`
- Release title: `YonerAI v0.1.0-alpha.1 Public Demo Slice`
- Release type: GitHub prerelease
- Current main after installer foundation: `563e669113dd0c6dc2255cd44bbc9c23822770c9`

No new GitHub Release or tag was created for this verification checkpoint.

## Public User Path Verified

The README dependency-inclusive quickstart was verified from a fresh clone of
`v0.1.0-alpha.1`:

```powershell
python -m pip install -r core/requirements.txt httpx
python -m pip install -e clients/cli
yonerai demo --json
yonerai demo --pretty
yonerai quickstart
```

Observed result:

- `yonerai demo --json` returned `ok: true`
- contract: `yonerai-public-demo/v1`
- schema version: `1.0`
- quickstart alias: `yonerai quickstart`
- `yonerai demo --pretty` printed the public demo sections
- `yonerai quickstart` printed the same public demo path

## Documentation Gap

The README and CLI README include the dependency-inclusive setup command. The
release page and `docs/releases/0.1.0-alpha.1.md` quickstart currently show only
the editable CLI install step, so a user following only the release body may
miss `core/requirements.txt` plus `httpx`. Treat the README/CLI README path as
the authoritative alpha quickstart until the release-note body is amended in a
future non-release-tag documentation PR.

## Boundary

This verification did not use Oracle, live Discord, provider API keys, Google
login, deployment, persistent memory, production signing keys, or production
trust stores. The Official Managed Cloud remains contract-only and external to
the public repository.

## Not Included

- no new GitHub Release
- no new tag
- no installer implementation
- no network-executing PowerShell installer
- no npm or winget publishing
- no production trust completion claim
- no `src/cogs/ora.py` resolution claim
