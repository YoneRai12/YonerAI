# YonerAI installer distribution foundation

Status: foundation plan. No network-executing installer is included here.

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

Release artifacts should use stable, versioned names:

- `YonerAI-<version>.zip` for the current public release archive.
- `YonerAI-<version>-windows-x64.zip` for a future Windows artifact.
- `YonerAI-<version>-manifest.json` for future signed manifest publishing.

Do not publish unversioned mutable installer artifacts as the primary install target.

## Doctor plan

A future `yonerai doctor` command should be non-mutating and offline by default. It should check:

- Python version compatibility.
- CLI import and command availability.
- `yonerai demo --json` availability.
- installed package version display.
- whether credentials are absent or ignored for public demo flows.
- manifest verification readiness when a manifest path is provided.

It must not modify PATH, download remote code, install packages, create credentials, deploy, or connect to live services.

## Implementation order

1. Land manifest schema, example, and validation tests.
2. Add a manifest reader/verifier that validates local files only.
3. Connect release workflow to publish a signed manifest artifact.
4. Add `yonerai doctor` as non-mutating validation.
5. Add dry-run installer planning.
6. Add PowerShell installer only after signature verification, rollback, logs, and safe mode are proven.
7. Add npm and winget bootstrap entry points that read the same manifest.

## Acceptance criteria

- Example manifest validates against the schema contract.
- Missing SHA256 is rejected.
- Invalid channel is rejected.
- Invalid target is rejected.
- Placeholder signature is allowed only when the manifest is explicitly non-production.
- Tests perform no network calls.
- No executable remote installer code is added.
