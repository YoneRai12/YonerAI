# YonerAI Validation Matrix

Use the smallest validation set that proves the touched lane, then expand when risk increases.

| Touched area | Minimal validation | Expanded validation |
| --- | --- | --- |
| Python runtime | `python -m pytest <targeted tests> -q`; `python -m ruff check <touched paths>`; `python -m compileall <touched paths>` | public smoke tests; related integration tests; old PR reproduction proof |
| `core/src/ora_core/hybrid` | hybrid/contract targeted tests; `ruff`; `compileall` | public capability boundary tests; replay/quarantine policy tests |
| Public API | targeted API tests; public runnable smoke | CLI/Web smoke against API; error redaction checks |
| CLI | targeted CLI tests with mocked requests | API smoke plus CLI end-to-end local loopback |
| Web | targeted frontend/API tests; safe error scan | browser smoke, responsive checks, console error review |
| Discord contract | synthetic contract tests only | duplicate responder, final once-only, same-message edit, reply-chain, files/download tests |
| `src/cogs/ora.py` extraction | characterization tests before edit; targeted tests after edit; `compileall` | public smoke; import side-effect review; behavior diff review |
| Dependency update | affected package tests; lockfile/package diff review | broader runtime smoke; advisory/changelog evidence |
| Docs-only | `git diff --check`; changed-file scans | link check/manual render review when public presentation changes |
| Root file move | reference scan for moved path; `git diff --check` | public/CLI smoke; docs update verification |
| Changelog checkpoint | checkpoint note scan; future-date scan; `git diff --check` | README/README_JP checkpoint link verification |
| Public release candidate | public runnable smoke; CLI smoke when included; Web smoke when included; future-date scan; `git diff --check` | `gh release list/view` for existing release state only; package/archive verification |

Always add:

- secret scan on changed files
- local absolute path / username / hostname scan on changed files
- mojibake / hidden Unicode scan on changed public text
- `src/cogs/ora.py` and `reference_clawdbot` diff confirmation when those are forbidden or not in scope
