# Guardrail Compression Policy 2026-05-21

Status: v7.7 implementation policy. This compresses process guardrails so code, tests, and acceptance harnesses become the default output.

## 1. HARD INVARIANTS

- Keep public, private, and control-plane boundaries separate.
- Do not put secrets, private runtime truth, live route maps, private runtime inventory, control-plane internals, break-glass details, raw chain-of-thought, usernames, hostnames, or local absolute paths in public artifacts.
- Keep Full Private Self-Host, Official Hybrid Private, and Official Managed Cloud compatible through explicit contracts and capability gates.
- Dangerous capabilities are deny-by-default.
- A signed envelope proves origin and integrity only; it does not imply trust or approval.
- The private Discord gateway is the canonical production reply source.
- Public PythonBot and old ORA residue must not become simultaneous production responders.
- Do not deploy, create production signing keys, create production trust stores, add production DB behavior, connect live Discord, require real Discord credentials, claim persistent memory completion, claim Google login completion, claim Discord restored, claim full hybrid completion, start v7.8, or claim production readiness.

## 2. IMPLEMENTATION GATES

- The design corpus is a constraint source, not a reason to avoid implementation.
- Prefer small code patches, regression tests, fixtures, and acceptance harnesses over new planning documents.
- A security/runtime PR is current only when the affected path exists on current main and the replacement has regression tests, targeted validation, or a clear non-reproducibility proof tied to current-main code.
- `src/cogs/ora.py` is not permanently forbidden. It requires a boundary extraction plan, behavior-preserving tests, and owner/private-runtime decisions before implementation changes.
- Discord restoration starts with contracts, event-shape tests, duplicate-responder tests, and file/download fixtures before any live token or runtime connection.
- Release notes are bundled by meaningful checkpoint, not every tiny PR.

## 3. DOCS-ONLY ALLOWED CASES

- A doc is allowed when it directly unblocks a code/test lane, records a hard blocker, or prevents a forbidden boundary crossing.
- A docs-only PR is not enough for an implementation goal unless every safe implementation lane is blocked with evidence.
- PR count is secondary to current-main security evidence.
- Triage docs may close stale confusion, but they should not replace reproducible tests or narrow patches.

## 4. THINGS WE STOP DOING

- Stop creating broad ledgers that do not reduce implementation uncertainty.
- Stop using design exactness gaps as a default reason to defer low-risk tests.
- Stop treating old PR count changes as the main deliverable.
- Stop mass-touching files to influence GitHub last-commit display.
- Stop writing release notes for every micro-change; group them into checkpoint releases.
- Stop describing guarded future work as completed runtime behavior.
