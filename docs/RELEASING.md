# Releasing YonerAI (Date-Based Versions)

Releases are now **date-based** and stored in `VERSION` using:

- `YYYY.M.D` (example: `2026.2.9`)

Git tags keep the existing `v*` prefix to reuse the GitHub Actions release workflow:

- Tag format: `v<VERSION>` (example: `v2026.2.9`)

## Release Checklist
1. Update `VERSION` to the new date version.
2. Write release notes at `docs/releases/<VERSION>.md`.
3. Update `CHANGELOG.md` (top entry) and optionally `docs/RELEASE_NOTES.md` (curated).
4. Commit:
   - `git add VERSION docs/releases/<VERSION>.md CHANGELOG.md docs/RELEASE_NOTES.md`
   - `git commit -m "Release <VERSION>"`
5. Tag and push:
   - `git tag -a v<VERSION> -m "YonerAI <VERSION>"`
   - `git push --tags`

## CI / GitHub Release
On tag push (`v*`), GitHub Actions will:
- Verify `VERSION` matches the tag (supports SemVer and DateVer).
- Create `<PRODUCT_NAME>-<VERSION>.zip` via `git archive` (`PRODUCT_NAME` file).
- Publish a GitHub Release named `<PRODUCT_NAME> <VERSION>` using `docs/releases/<VERSION>.md` as the body.
