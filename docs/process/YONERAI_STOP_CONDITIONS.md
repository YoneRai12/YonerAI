# YonerAI Stop Conditions and Anti-Patterns

## Hard Stop Conditions

Stop the current lane when:

- dirty state cannot be preserved without loss
- GitHub state cannot be verified
- the action needs live Discord, deploy, production signing keys, production trust stores, persistent memory, Google login, production DB behavior, private runtime truth, or control-plane internals
- the action touches `reference_clawdbot`
- the same test category fails twice
- unresolved P0/P1/security/correctness review remains
- owner approval is required and not already given

## Soft Blocks

Document and switch to an independent lane when:

- an old PR cannot be safely reproduced
- a dependency update is too broad for available tests
- public HTML appears stale but `gh` state is verified
- a release is ambiguous
- `src/cogs/ora.py` extraction needs characterization tests first

## Continue With Independent Lane When

- the fallback lane does not depend on the blocked PR
- validation can be run without private/live credentials
- scope remains one PR and one lane

## Do Not Ask Owner When

- the repo already has enough current-main evidence to make a safe narrow patch
- a docs/process change is public-safe and non-runtime
- an automated review is only a quota/status warning
- a stale PR is clearly superseded by a merged current-main patch and tests

## Owner Decision Required When

- behavior crosses private/runtime/control-plane boundaries
- live Discord or real credentials are needed
- persistent memory, Google login, production DB, deploy, or production signing/trust is involved
- moving active root entrypoints or config could break users
- broad ORA/YonerAI runtime rename is proposed

## Anti-Patterns

- huge docs-only goals that avoid implementation
- broad rename without compatibility tests
- stale PR merge without current-main reproduction
- mass root moves
- PR count obsession over security evidence
- release for every tiny PR
- treating design docs as a reason to avoid implementation
- treating safety as a reason to never touch `src/cogs/ora.py`
- manipulating GitHub root last-commit messages by mass-touching files
- adding claims because a plan exists rather than because code/tests landed
- creating GitHub Releases for internal checkpoints, docs-only/process-only work, ledgers, root inventory, or PR-count reconciliation
- continuing date-suffix checkpoint releases when no runnable public milestone is being shipped
