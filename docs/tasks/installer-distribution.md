# YonerAI installer distribution foundation

Status: foundation plan with local manifest verification, doctor/status
diagnostics, dry-run install planning, and human-readable
Japanese-capable CLI output.
No network-executing installer is included here.

## Purpose

YonerAI distribution should converge on an installer bootstrap system, not an npm-only or pip-only install story.

PowerShell, npm, winget, and GitHub Releases are multiple entry points into the same signed release manifest. The signed release manifest is the distribution source of truth. Git clone of `main` remains valid for developers, contributors, Codex, and CI, but it is not the production install mechanism.

## Distribution model

The release manifest describes each artifact, target platform, digest, signature status, and minimum requirements. Installers and bootstrappers must read the manifest, verify it, and fail closed before using any artifact.

Entry points:

- PowerShell installer: future Windows-first onboarding surface.
- npm `@yonerai/cli`: future thin bootstrapper that resolves the same manifest.
- winget: future official Windows channel that points at a verified release artifact.
- GitHub Releases: release artifact hosting and human-facing release history.
- Manual path: users can download an artifact and verify the manifest, hash, and signature without executing a remote script.

## Required checks

All installer implementations must include:

- SHA256 verification before use.
- Signature verification before use.
- Fail-closed behavior when manifest, hash, signature, channel, or target validation fails.
- Rollback plan for previously installed working versions.
- Update plan that preserves user data and avoids silent production migrations.
- Install logs that avoid secrets, usernames, hostnames, private runtime inventory, and local absolute paths in public reports.
- Least privilege by default.
- Safe install variant that performs validation and prints planned actions without mutating the machine.
- Manual verification path documented beside the automated path.

## Non-goals for this foundation

- No `install/windows.ps1`.
- No `irm ... | iex` usage.
- No download-and-execute code.
- No npm package publishing.
- No winget manifest publishing.
- No production signing key generation.
- No production trust store creation.
- No deployment, Oracle, live Discord, Google login, persistent memory, production DB, telemetry ingestion, or external provider live generation.

## Manifest relationship

`releases/manifest.schema.json` defines the future installer bootstrap release manifest. `releases/manifest.example.json` is an example contract fixture and is not a production installer manifest.

The existing `core/src/ora_core/distribution/release.py` sidecar models remain the current Distribution Node MVP verification implementation. The installer bootstrap manifest is the future distribution source of truth for public install entry points and should be connected to signed sidecars in a later implementation PR.

## Artifact naming policy

Release artifacts should use stable, versioned names. The local manifest
validator enforces the known alpha naming policy for source archives, future
Windows x64 archives, and future manifest assets.

- `YonerAI-<version>.zip` for the current public release archive.
- `YonerAI-<version>-windows-x64.zip` for a future Windows artifact.
- `YonerAI-<version>-manifest.json` for future signed manifest publishing.

Do not publish unversioned mutable installer artifacts as the primary install target.

## Doctor plan

`yonerai doctor` is the first non-mutating diagnostic command. It is offline by
default and checks:

- Python version compatibility.
- CLI import and command availability.
- `yonerai demo` / `yonerai quickstart` command availability.
- installed package version display.
- whether credentials are absent or redacted for public demo flows.
- local manifest example verification readiness.
- public-safe redaction self-check.
- Tools/MCP deny-policy self-check.
- English and Japanese human-readable output with stable English-keyed JSON.

It must not modify PATH, download remote code, install packages, create credentials, deploy, or connect to live services.

`yonerai status` is the shorter public demo / installer-readiness view over the
same offline checks. It is not an installer and does not mutate the machine.

## Manifest verify plan

`yonerai manifest verify <path>` is local-file validation only. It checks the
manifest contract, channel, version, target, SHA256 format, signature state, and
optional local artifact SHA256/size mappings. It rejects remote manifest URLs and
does not download, execute, install, or mutate anything.

Pretty output reports contract validity, install readiness, artifact count,
SHA256/signature status, placeholder warnings, and the fact that no
network/download/install action was performed. `--lang ja` changes only
human-readable output.

The alpha example manifest is expected to be contract-valid but not install-ready
because it uses `placeholder_non_production` signature material. A production
installer must require signed manifests and fail closed when the signature is not
verified.

## Implementation order

1. Land manifest schema, example, and validation tests. Done for the alpha foundation.
2. Add a manifest reader/verifier that validates local files only. Done for local contract verification.
3. Add `yonerai doctor` as non-mutating validation. Done for local alpha diagnostics.
4. Add `yonerai status`, Japanese pretty output, and manifest pretty output. Done for CLI experience diagnostics.
5. Add dry-run installer planning with no download, execution, PATH mutation, or install mutation. Done for `yonerai install plan` and the Windows-specific `yonerai install plan-windows` alias.
6. Connect release workflow to publish a signed manifest artifact.
7. Add signature verification against an explicit production trust source.
8. Add PowerShell bootstrap skeleton only after signature verification, rollback, logs, and safe mode are proven.
9. Add npm and winget bootstrap entry points that read the same manifest.

## Next safe milestone

The dry-run Windows installer planner and release artifact naming validation now
exist. The next safe milestone is manifest-to-release-asset consistency checks,
followed by install/update dry-run commands that still consume local manifests
only. These steps must avoid remote code execution, PATH mutation, auto-download,
npm publishing, winget publishing, production signing key generation, and
production trust store creation.

## Issue #313 tracking state

Issue #313 remains open as the parent installer bootstrap tracking issue.
The original manifest-first definition is partly complete, but installer
implementation work remains and is now represented by linked child issues.

Completed or substantially completed:

- Manifest schema: PR #307, `releases/manifest.schema.json`.
- Manifest example: PR #307, `releases/manifest.example.json`.
- Local manifest verification: PR #309, `yonerai manifest verify`.
- Doctor diagnostics: PR #309 and PR #311, `yonerai doctor`.
- Installer distribution foundation doc: PR #307.
- Windows dry-run planning foundation: PR #320, `yonerai install plan-windows`.
- Unified local install dry-run planning: current lane, `yonerai install plan`.
- Release artifact naming validation foundation: PR #326.

Remaining child issues:

- #328 `feat: implement signed manifest verification`.
- #329 `feat: add yonerai install/update dry-run commands` (partially complete after `yonerai install plan`; `yonerai update plan` remains).
- #330 `feat: add PowerShell dry-run installer skeleton`.
- #331 `docs: define safe install and uninstall flow`.
- #332 `feat: validate release artifact hashes and naming`.
- #333 `docs: define installer signing and key rotation lifecycle`.
- #334 `docs: prepare install.yonerai.com onboarding page`.

The parent issue should stay open until the child issues are complete or the
owner explicitly approves closing it as a pure index. See
`docs/changelog/checkpoints/issue-313-installer-triage.md` and
`docs/changelog/checkpoints/issue-313-installer-tracking.md`.

## Acceptance criteria

- Example manifest validates against the schema contract.
- Missing SHA256 is rejected.
- Invalid channel is rejected.
- Invalid target is rejected.
- Placeholder signature is allowed only when the manifest is explicitly non-production.
- Tests perform no network calls.
- No executable remote installer code is added.
- Root README, Japanese README, and CLI README document the same public-safe CLI
  diagnostic surface.
