# Release Note Style Guide

Status: v7.7 public checkpoint style guide.

## Purpose

YonerAI release notes should read like professional product/research repository checkpoints. They must be clear enough for a new reader, traceable enough for maintainers, and strict enough to avoid production or feature-completion claims.

## Required Structure

Use this structure for new public checkpoint notes:

1. Summary
2. Highlights
3. User-visible changes
4. Developer / API / CLI changes
5. Security and boundary changes
6. Repository / presentation changes
7. Validation
8. Known limitations
9. Not included
10. Traceability

Sections may be marked `None` when there is no content, but the note should not hide limitations.

## Naming

- Titles should describe the checkpoint, not the PR number.
- Use same-day suffixes monotonically: `vYYYY.M.D`, `vYYYY.M.D.1`, `vYYYY.M.D.2`, and so on.
- Do not create future-dated tags or markdown checkpoint titles.
- Do not delete or retag existing historical releases without explicit owner approval.
- If GitHub Releases and markdown checkpoint notes diverge, say which one is the GitHub latest and which one is the latest markdown checkpoint.

## Traceability

- Put PR numbers, commit SHAs, and branch names in a final `Traceability` section.
- Do not lead a release title or first paragraph with PR numbers.
- Keep validation commands near the release note body, not only in PR comments.

## Non-Claims

Every checkpoint that touches public capabilities must clearly avoid claiming production readiness, shipping completion, official cloud completion, hybrid completion, persistent memory completion, Google login completion, Discord gateway completion, Tools/MCP completion, provider ecosystem completion, final Web UI completion, or `src/cogs/ora.py` resolution unless a dedicated approved lane proves that claim.
