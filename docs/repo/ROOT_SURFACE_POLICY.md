# Root Surface Policy

Status: public-safe repository hygiene policy. This document does not move runtime files by itself.

## Purpose

The repository root should make YonerAI look like a professional public distribution-core project without hiding current runtime boundaries or breaking active scripts. Some legacy runtime files still use ORA names; root policy should preserve those references until a dedicated rename or extraction lane updates them safely.

Root cleanup must preserve the v7.7 implementation anchor:

- provider independence
- same experience across official, local, and self-host modes
- approval-gated self-evolution product intelligence
- privacy-preserving learning
- lane separation between public, private runtime, and official control plane

This policy is not a production-readiness claim.

## Keep In Root

Keep root files when they are standard repository entrypoints, active project identity files, packaging/test config, or actively referenced runtime launchers.

Examples:

- `README.md`
- `README_JP.md`
- `LICENSE`
- `CONTRIBUTING.md`
- `CHANGELOG.md`
- `VERSION`
- `PRODUCT_NAME`
- `AGENTS.md`
- `.env.example`
- `.gitignore`
- `pyproject.toml`
- `pytest.ini`
- `requirements.txt`
- `requirements-optional-memory.txt`
- `Dockerfile`
- active compose files
- active launchers referenced by scripts or docs

## Directory Policy

Root directories should have clear ownership:

- `.github`: GitHub workflows and templates
- `core`: public Core API
- `clients`: temporary/demo clients and public-safe clients
- `docs`: public-safe docs and checkpoint notes
- `scripts`: public-safe scripts
- `tools`: developer or maintenance tools
- `tests`: test suite
- `src`: legacy/runtime code that still needs boundary-specific lanes
- `assets`, `config`, `templates`, `memory`, `data`: keep until reference audit proves a safe move or retirement

Local-only ignored cache/state directories such as `.venv`, `.pytest_cache`, `.ruff_cache`, and `data` must not be treated as GitHub-visible root product surface unless they are tracked.

## Move Candidates

Move a root file only when all are true:

- references are found and updated
- tests or smoke checks cover the move
- no runtime behavior changes silently
- no private/control-plane internals are exposed
- no local absolute paths or secrets are introduced

Suggested future homes:

- public-safe developer helpers: `tools/` or `scripts/`
- public-safe config examples: `config/`
- long-form repo policy: `docs/repo/`
- retired notes: `docs/legacy/`

Debug helpers that read local state files must not embed a user or machine path. Prefer an environment variable with a repository-relative fallback, and keep the helper under `tools/debug/` instead of the repository root.

## Do Not Touch In Generic Cleanup

- `reference_clawdbot`
- `src/cogs/ora.py`
- dirty quarantine branches or worktrees
- deployment or production config as a behavior change
- private runtime implementation
- control-plane internals

`reference_clawdbot` is classified separately as a gitlink/submodule residue and must not be initialized, repaired, removed, or replaced in generic root cleanup.

Root helpers that can affect legacy runtime files, such as `remove_legacy.ps1`, should be treated as `DO_NOT_RUN / RETIRE_CANDIDATE` until a dedicated owner-approved lane validates their behavior. A generic root cleanup must not run or move them just to make the file list look cleaner.

## Product Presentation

README first-screen content, release titles, and current checkpoint summaries should use capability names rather than PR-number-first wording. PR numbers belong in traceability sections, maintenance ledgers, or PR bodies, not in the product-facing headline.

See [Public Presentation Policy](PUBLIC_PRESENTATION_POLICY.md) and [Release Date Hygiene Policy](RELEASE_DATE_HYGIENE_POLICY.md).

## Required Validation

Before any root movement PR:

- inspect actual references with static search
- update references when moving files
- run targeted tests for touched surfaces
- run `git diff --check`
- run changed-file secret scan
- run changed-file local path / username scan
- confirm `src/cogs/ora.py` is unchanged
- confirm `reference_clawdbot` is unchanged

## Non-Claims

Root-surface cleanup does not claim:

- production readiness
- official-cloud completion
- hybrid completion
- persistent memory completion
- final Web UI completion
- Google login completion
- Discord gateway completion
- `src/cogs/ora.py` resolution
