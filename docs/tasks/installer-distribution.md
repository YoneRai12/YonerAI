# YonerAI installer distribution foundation

Status: public alpha foundation plan with local manifest verification,
doctor/status diagnostics, dry-run install planning, non-production/test trust
verification only, and human-readable Japanese-capable CLI output. No
network-executing installer is included here.

## Purpose

YonerAI distribution should converge on an installer bootstrap system, not an npm-only or pip-only install story.

PowerShell, npm, winget, and GitHub Releases are future entry points into the
same signed release manifest. The release manifest is the distribution source
of truth, but this public repository only defines the public schema, local
verification, dry-run planning, hash checks, and non-production/test trust
fixtures. Production signing keys, production trust stores, key rotation, and a
release signing service belong to a future private/official lane. Git clone of
`main` remains valid for developers, contributors, Codex, and CI, but it is not
the production install mechanism.

## Distribution model

The release manifest describes each artifact, target platform, digest,
signature status, and minimum requirements. Public alpha commands may validate
local manifests, hashes, artifact names, and non-production/test signatures.
They must report production signatures as unavailable unless an explicit
official/private trust source exists outside the public repo. Production-capable
installers and bootstrappers must read the manifest, verify it against an
official trust source, and fail closed before using any artifact.

Entry points:

- PowerShell installer: future Windows-first onboarding surface.
- npm `@yonerai/cli`: future thin bootstrapper that resolves the same manifest.
- winget: future official Windows channel that points at a verified release artifact.
- GitHub Releases: release artifact hosting and human-facing release history.
- Manual path: users can download an artifact and verify the manifest, hash, and signature without executing a remote script.

## Required checks

Public alpha installer-facing commands must include:

- SHA256 verification before use.
- Non-production/test signature verification only when an explicit test trust
  fixture is provided.
- Fail-closed behavior when manifest, hash, signature, channel, or target validation fails.
- Clear `not install-ready` status when production signature verification is
  unavailable.
- No production signing keys or production trust stores in the public repo.
- Safe install variant that performs validation and prints planned actions without mutating the machine.
- Manual verification path documented beside the automated path.

Production-capable installers in a future private/official lane must additionally
include:

- Production signature verification before use.
- Production trust source/key lifecycle outside the public repository.
- Rollback plan for previously installed working versions.
- Update plan that preserves user data and avoids silent production migrations.
- Install logs that avoid secrets, usernames, hostnames, private runtime inventory, and local absolute paths in public reports.
- Least privilege by default.

## Non-goals for this foundation

- No `install/windows.ps1`.
- No `irm ... | iex` usage.
- No download-and-execute code.
- No npm package publishing.
- No winget manifest publishing.
- No production signing key generation.
- No production trust store creation.
- No production signing key, production trust store, key rotation, or release
  signing service implementation in the public repository.
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
SHA256/signature status, placeholder warnings, optional non-production/test
trust fixture checks, and the fact that no network/download/install action was
performed. `--lang ja` changes only human-readable output.

The alpha example manifest is expected to be contract-valid but not install-ready
because it uses `placeholder_non_production` signature material. Public alpha
verification supports deterministic non-production/test trust fixtures with
`--test-trust-fixture`, but it must not treat them as production trust. A
production-capable installer in a future private/official lane must require
signed manifests and fail closed when the production signature is not verified
against the official trust source.

## Implementation order

1. Land manifest schema, example, and validation tests. Done for the alpha foundation.
2. Add a manifest reader/verifier that validates local files only. Done for local contract verification.
3. Add `yonerai doctor` as non-mutating validation. Done for local alpha diagnostics.
4. Add `yonerai status`, Japanese pretty output, and manifest pretty output. Done for CLI experience diagnostics.
5. Add dry-run installer planning with no download, execution, PATH mutation, or install mutation. Done for `yonerai install plan` and the Windows-specific `yonerai install plan-windows` alias.
6. Add public alpha signed-manifest verification against an explicit
   non-production/test trust fixture only. Done for local test-fixture
   verification.
7. Add `yonerai update plan` and manifest-to-release-asset consistency checks
   without live network use by default. Done for local-manifest update planning;
   manifest-to-release-asset consistency checks remain a separate public task.
8. Add PowerShell dry-run bootstrap skeleton only after local verification,
   rollback planning, logs, and safe mode are specified.
9. Future private/official lane: connect release workflow to a signing service,
   publish a signed manifest artifact, define production trust/key rotation, and
   verify signatures against the official trust source.
10. Future private/official lane: add npm and winget bootstrap entry points that
    read the same manifest.

## Next safe milestone

The dry-run Windows installer planner and release artifact naming validation now
exist, `yonerai install plan` consumes a local manifest without installing
anything, `yonerai update plan` compares local `VERSION` with a local manifest
without mutating the machine, and `yonerai manifest verify` can verify signed
test manifests against an explicit non-production trust fixture. The next safe
milestone is manifest-to-release-asset consistency checks. These steps must
avoid remote code execution, PATH mutation, auto-download, npm publishing,
winget publishing, production signing key generation, and production trust
store creation.

## Issue #313 tracking state

Issue #313 remains open as the parent installer bootstrap tracking issue.
The original manifest-first definition is partly complete, but installer
implementation work remains. On 2026-05-22, child issues #328 through #334 were
closed as noisy duplicate trackers and consolidated back into #313. They remain
historical references only; active tracking is now on #313.

Completed or substantially completed:

- Manifest schema: PR #307, `releases/manifest.schema.json`.
- Manifest example: PR #307, `releases/manifest.example.json`.
- Local manifest verification: PR #309, `yonerai manifest verify`.
- Doctor diagnostics: PR #309 and PR #311, `yonerai doctor`.
- Installer distribution foundation doc: PR #307.
- Windows dry-run planning foundation: PR #320, `yonerai install plan-windows`.
- Local install dry-run planning: PR #336, `yonerai install plan`.
- Local update dry-run planning: PR #341, `yonerai update plan`.
- Local non-production/test signed manifest verification:
  `yonerai manifest verify <path> --test-trust-fixture <fixture>`.
- Release artifact naming validation foundation: PR #326.

Remaining tasks are tracked directly in #313:

- PowerShell dry-run installer skeleton that validates local inputs and prints planned actions only.
- Safe install, rollback, update, and uninstall docs.
- Manifest-to-release-asset hash and naming validation.
- Public documentation that separates non-production/test trust fixtures from
  future private/official production signing, trust source, key rotation, and
  release signing service work.
- Future install.yonerai.com / yonerai.com/install onboarding copy that does not present remote execution as ready-to-run behavior.

The parent issue should stay open until the checklist in #313 is complete or
the owner explicitly approves a different tracking model. See
`docs/changelog/checkpoints/issue-313-installer-triage.md` and
`docs/changelog/checkpoints/issue-313-installer-tracking.md`.

## Acceptance criteria

- Example manifest validates against the schema contract.
- Missing SHA256 is rejected.
- Invalid channel is rejected.
- Invalid target is rejected.
- Placeholder signature is allowed only when the manifest is explicitly non-production.
- Public alpha trust verification uses non-production/test trust fixtures only.
- Production signing keys, production trust stores, key rotation, and release
  signing service behavior remain outside the public repository.
- Tests perform no network calls.
- No executable remote installer code is added.
- Root README, Japanese README, and CLI README document the same public-safe CLI
  diagnostic surface.
