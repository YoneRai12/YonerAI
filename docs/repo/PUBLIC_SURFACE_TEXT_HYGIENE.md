# Public Surface Text Hygiene

Status: v7.7 public repository text policy.

## Purpose

YonerAI public-facing text should be readable, traceable, and stable across GitHub surfaces. This policy covers PR titles and bodies, release notes, README first-screen text, root-facing docs, and future public commit subjects.

This policy does not change runtime behavior. It supports provider independence, same-experience language, public/private/control-plane separation, approval-gated self-evolution, and privacy-preserving learning without claiming production readiness.

## PR Titles and Bodies

- Use product-facing titles such as `docs: reconcile PR backlog state` or `fix: harden local LLM error reporting`.
- Do not lead PR titles or opening summaries with PR numbers.
- Put PR numbers, merge commits, and related links in a late `Traceability` section.
- Prefer concise English PR bodies when GitHub rendering or automation may corrupt Japanese text.
- Japanese is allowed when verified as UTF-8 and when it is needed for user-facing clarity.
- Never leave repeated question marks, replacement characters, or mojibake in a merged PR body when it can be edited or corrected with a follow-up comment.

## Release Notes

- Release titles should describe the user-visible checkpoint, not the internal PR number.
- Use a stable structure: Summary, Highlights, User-visible changes, Developer/API/CLI changes, Security and boundary changes, Validation, Known limitations, Not included, Traceability.
- Same-day checkpoint suffixes must be monotonic: `vYYYY.M.D`, `vYYYY.M.D.1`, `vYYYY.M.D.2`, and so on.
- Do not publish future-dated checkpoint links as the current/latest checkpoint.

## Hidden Unicode and Mojibake Ban

Maintained public docs must not contain:

- repeated question-mark mojibake such as `????`;
- Unicode replacement characters;
- common mojibake fragments such as `ã`, `縺`, `鬆`, `譁`, `繧`, `蟆`, `荳`, or `驥` unless the file is explicitly documenting mojibake;
- bidirectional or hidden control characters U+202A through U+202E, U+2066 through U+2069, U+200B, U+200C, U+200D, or U+FEFF.

Suggested scans:

```bash
rg -n "(\?\?\?\?|�|ã|縺|鬆|譁|繧|蟆|荳|驥)" README.md README_JP.md docs .github
python - <<'PY'
from pathlib import Path
bad = []
for path in [Path(p) for p in ["README.md", "README_JP.md"] + [str(p) for p in Path("docs").rglob("*") if p.is_file()]]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    for index, char in enumerate(text):
        cp = ord(char)
        if 0x202A <= cp <= 0x202E or 0x2066 <= cp <= 0x2069 or cp in {0x200B, 0x200C, 0x200D, 0xFEFF}:
            bad.append(f"{path}:{index}:U+{cp:04X}")
print("\n".join(bad))
PY
```

## Commit Subjects

- New commit subjects should describe the change, not the PR number.
- Do not rewrite old commits only to remove auto-linked PR numbers.
- GitHub's native PR number display is normal UI and is not a cleanup target.

## Non-Claims

Text hygiene does not claim production readiness, shipping completion, official cloud completion, hybrid completion, persistent memory completion, Google login completion, Discord gateway completion, Tools/MCP completion, provider ecosystem completion, or `src/cogs/ora.py` resolution.
