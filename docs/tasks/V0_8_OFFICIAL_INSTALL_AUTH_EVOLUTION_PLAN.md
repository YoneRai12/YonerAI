# YonerAI v0.8 Official Install/Auth/Evolution Boundary Plan

Status: active v0.8 alpha implementation plan.

This plan advances YonerAI from the v0.7 official bridge foundation toward a
public-safe install/auth/privacy/self-evolution boundary. It does not make the
public repository the production cloud, production Oracle, production Google
login, production installer, or production self-evolution system.

## Source Truth

- Current base: `v0.7.0-alpha.1`
- Target prerelease if the gate passes: `v0.8.0-alpha.1`
- Stable release: not allowed unless the owner explicitly approves a stable
  gate after evidence.
- Public repo role: contract-first distribution core and local CLI runtime.
- Private/official role: production Oracle, production auth/account linking,
  production self-evolution, signing key lifecycle, and release signing service.

## Public/Private Boundary

| Area | Public v0.8 alpha may include | Private/official lane only |
| --- | --- | --- |
| Install | plan-first `install.ps1`, explicit local `install-local.ps1`, local manifest verification, dry-run install/update plans | production network installer, production signing service, production trust store, PATH mutation defaults |
| Google auth | dry-run contract, PKCE/state/loopback/minimal scopes, no token printing | production account login, account linking, refresh token storage |
| OpenAI shared traffic | off-by-default policy, public/safe-only contract, ledger flag visibility | enabled shared traffic, quota-backed usage, owner/org eligibility decisions |
| Self-evolution | synthetic fixtures, proposal queue, approval states, no mutation | production signal ingestion, support feedback ingestion, automatic patch candidate lanes, official release/social drafting |
| Official cloud | docs/contracts and visible boundary | runnable managed cloud production |

## Milestones

1. Current truth and security intake
   - Verify GitHub releases, PRs, and current main.
   - Do not merge stale PRs blindly.
   - P0/P1/security review blocks release.

2. Self-evolution boundary correction
   - Keep public self-evolution proposal-only.
   - Reject raw prompts, completions, PII-like fields, local paths, live URLs,
     GitHub mutation fields, deploy fields, and release mutation fields.
   - Add `docs/contracts/OFFICIAL_SELF_EVOLUTION_BOUNDARY.md`.
   - Add `docs/private_handoff/YONERAI_ORACLE_SELF_EVOLUTION_HANDOFF.md`.

3. yonerai.com install/release/press foundation
   - Keep GitHub Release as distribution source.
   - Add future v0.8 page/card content contracts.
   - Do not deploy secrets or claim live site deployment.

4. Safe one-command install progression
   - `install.ps1` remains dry-run by default.
   - It may read a local manifest and print artifact/signature/trust status.
   - It must not download, execute remote code, mutate PATH, edit registry,
     install services, request admin, or install packages.

5. Manifest/artifact/trust
   - v0.8 manifest is release-gate material.
   - The final release manifest must record `YonerAI-0.8.0-alpha.1.zip`,
     SHA256, size, versioned asset name, and non-production/test trust status
     unless production trust is delivered in a private lane.
   - No fake production signature.

6. Google auth foundation
   - `yonerai auth status` remains status-only.
   - `yonerai auth google login --dry-run` remains dry-run-only in public repo.
   - No embedded webview, token print, token exchange, or refresh token storage.

7. Shared traffic policy
   - OpenAI shared traffic is off by default.
   - Private/local file/local node/memory content is excluded.
   - User opt-in, quota, and eligibility are future owner decisions.

8. CLI/TUI integration
   - Japanese-first `/認証`, `/プライバシー`, `/自己進化`, and `/更新`
     screens show the current local-only/dry-run/proposal-only state.
   - English aliases remain supported.

9. Quality Wall
   - Run targeted tests for TUI, auth/privacy, self-evolution, installer,
     manifest, release gate, and local path/secret/mojibake scans.

10. Release gate
    - Set `VERSION` to `0.8.0-alpha.1` only when the gate is ready.
    - Create `docs/releases/0.8.0-alpha.1.md`.
    - Build `YonerAI-0.8.0-alpha.1.zip`.
    - Update `releases/manifest.v0.8.0-alpha.1.json` with exact SHA256/size.
    - Run `python scripts/release_gate.py --tag v0.8.0-alpha.1 --artifact YonerAI-0.8.0-alpha.1.zip --github-prerelease true`.
    - Create GitHub prerelease only if the gate passes.

## Acceptance Criteria

- Public repo has no production Oracle/cloud/auth/signing/trust material.
- Public repo stores no provider key, OAuth token, refresh token, or production
  token material.
- `install.ps1` is plan-only and proves non-actions in tests.
- `install-local.ps1` remains explicit local install only.
- Google auth is dry-run/contract only.
- OpenAI shared traffic is disabled by default.
- Self-evolution remains proposal-only and cannot mutate code, GitHub,
  releases, deploys, or production configuration.
- TUI Japanese screens do not expose mojibake.
- Release notes, if created, are operation-manual style.

## Validation Commands

```powershell
pytest tests/test_cli_interactive_v030.py tests/test_self_evolution_queue_cli.py tests/test_official_bridge_foundation.py tests/test_local_bootstrap_script.py -q
pytest tests/test_auth_privacy_policy.py tests/test_release_manifest_schema.py tests/test_release_manifest_test_trust.py tests/test_release_gate.py -q
python -m py_compile clients/cli/yonerai_cli/interactive.py clients/cli/yonerai_cli/tui.py
git diff --check
python scripts/ci_quality_scans.py --changed
```

## Blockers

- Any unresolved P0/P1/security review.
- Missing exact v0.8 release asset hash/size at release gate.
- Any claim that public v0.8 is production cloud, production Oracle,
  production Google login, live Discord, production installer, npm/winget,
  persistent memory complete, or automatic self-evolution.
