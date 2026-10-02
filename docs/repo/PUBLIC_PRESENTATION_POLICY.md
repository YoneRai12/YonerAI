# Public Presentation Policy

Status: public-safe GitHub surface policy for README, release, and root-facing content.

## Purpose

The public GitHub surface should make YonerAI look like a professional product/research repository while staying honest about current limits. The first screen should explain product identity, current MVP capability, safe trial paths, and non-claims without exposing operational clutter.

## Product-Facing Surfaces

These surfaces should avoid implementation clutter and internal numbering:

- README first screen;
- README_JP first screen;
- GitHub Release title and opening summary;
- current checkpoint summaries;
- root-visible policy docs;
- root file names and last-commit subjects when new commits are created.

Use capability names such as `Local LLM Provider Compatibility`, `Conversation Session Scaffold`, or `Hybrid Connector Fixture` instead of PR-number-first wording.

## Traceability Surfaces

PR numbers are acceptable when they are clearly traceability, not product presentation:

- PR bodies;
- changelog/audit sections;
- maintenance ledgers;
- traceability matrices;
- late `Traceability` sections in release notes.

GitHub-native PR numbers on PR pages are normal GitHub UI and are not a cleanup target.

## Future Commit Subjects

New public-facing commit subjects should not contain literal PR numbers. Prefer product-facing conventional commits such as:

- `docs: release date hygiene policyを追加`
- `docs: public repository surface policyを更新`
- `docs: zero-trust practicality matrixを追加`

Existing commit history is not rewritten just to remove old auto-linked PR numbers.

## Non-Claims

Presentation cleanup does not claim production readiness, final Web UI, official cloud completion, full hybrid completion, or `src/cogs/ora.py` resolution.
