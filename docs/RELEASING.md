# Releasing YonerAI

YonerAI now uses semantic releases for public CLI runtime milestones. Stable
local-runtime releases use tags such as `v0.5.1`; alpha/beta/rc releases use
standard pre-release suffixes.

GitHub Releases must follow `docs/process/YONERAI_RELEASE_GOVERNANCE.md`. Do
not create a release for docs-only checkpoints, process ledgers, or PR-count
cleanup.

## Release checklist

1. Update `VERSION`.
2. Update `clients/cli/pyproject.toml` so the installed `yonerai` package reports
   the same version.
3. Write release notes at `docs/releases/<VERSION>.md`.
4. Update `CHANGELOG.md` and `docs/RELEASE_NOTES.md`.
5. Create or update `releases/manifest.v<VERSION>.json`.
6. Run local validation and CI.
7. Create `YonerAI-<VERSION>.zip` with:

   ```powershell
   python scripts/create_release.py <VERSION>
   ```

8. Compute the SHA256 and size of the generated ZIP, then update
   `releases/manifest.v<VERSION>.json`.
9. Rebuild the ZIP and confirm the SHA256/size did not change. Release-specific
   manifests are excluded from generated source archives through `.gitattributes`
   to avoid a manifest/hash feedback loop.
10. Create the GitHub Release only after the release gate passes.

## Manual GitHub Release command shape

Use the verified date and product-facing title required by the release goal.
For example:

```powershell
gh release create v0.5.1 YonerAI-0.5.1.zip `
  --title "2026.05.26 — YonerAI CLI Local Runtime v0.5.1 Distribution Trust Update" `
  --notes-file docs/releases/0.5.1.md `
  --target <verified-main-commit> `
  --latest
```

Do not mark stable CLI Local Runtime releases as prereleases unless the release
goal says to do so.

## Boundaries

- Do not create production signing keys or production trust stores.
- Do not implement `irm ... | iex` or a network download-and-execute installer.
- Do not mutate PATH by default.
- Do not publish npm or winget packages until a dedicated distribution lane
  proves that path.
- Do not claim production Oracle, Official Managed Cloud, live Discord, or full
  YonerAI production readiness from a local CLI release.
