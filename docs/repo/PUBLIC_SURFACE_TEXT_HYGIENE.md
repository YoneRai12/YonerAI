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
- Never leave four consecutive question marks, Unicode replacement characters, or mojibake in a merged PR body when it can be edited or corrected with a follow-up comment.
- If a merged PR body is editable, replace corrupted text with clean UTF-8 English or verified UTF-8 Japanese. If the body cannot be safely edited, add a clean follow-up comment and update the maintained ledger.

## Release Notes

- Release titles should describe the user-visible checkpoint, not the internal PR number.
- Use a stable structure: Summary, Highlights, User-visible changes, Developer/API/CLI changes, Security and boundary changes, Validation, Known limitations, Not included, Traceability.
- Same-day checkpoint suffixes must be monotonic: `vYYYY.M.D`, `vYYYY.M.D.1`, `vYYYY.M.D.2`, and so on.
- Do not publish future-dated checkpoint links as the current/latest checkpoint.

## Hidden Unicode and Mojibake Ban

Maintained public docs must not contain:

- four consecutive question marks used as corrupted replacement text;
- Unicode replacement characters, recorded as code point U+FFFD;
- common mojibake fragments, recorded in scan tooling by code point or escaped form rather than pasted as corrupted display text;
- bidirectional or hidden control characters U+202A through U+202E, U+2066 through U+2069, U+200B, U+200C, U+200D, or U+FEFF.

Suggested PowerShell-safe scan:

```powershell
@'
from pathlib import Path

marker_codepoints = {
    "question_mark_sequence": "?" * 4,
    "replacement_character": "\ufffd",
    "latin_mojibake_a_tilde": "\u00e3",
    "mojibake_ko": "\u7e3a",
    "mojibake_bin": "\u9b06",
    "mojibake_bun": "\u8b41",
    "mojibake_ru": "\u7e67",
    "mojibake_mushi": "\u87c6",
    "mojibake_sou": "\u8373",
    "mojibake_ki": "\u9a65",
}
hidden = set(range(0x202A, 0x202F)) | set(range(0x2066, 0x206A)) | {
    0x200B,
    0x200C,
    0x200D,
    0xFEFF,
}
paths = [p for p in [Path("README.md"), Path("README_JP.md")] if p.is_file()]
paths += [p for p in Path("docs").rglob("*") if p.is_file()]
paths += [p for p in Path(".github").rglob("*") if p.is_file()]

for path in paths:
    if path.suffix.lower() not in {"", ".md", ".txt", ".csv", ".json", ".yml", ".yaml"}:
        continue
    text = path.read_text(encoding="utf-8", errors="replace")
    for name, marker in marker_codepoints.items():
        if marker in text:
            print(f"{path}: marker:{name}")
    for index, char in enumerate(text):
        if ord(char) in hidden:
            print(f"{path}: hidden:{index}:U+{ord(char):04X}")
'@ | python -
```

## GitHub Warning Response

When GitHub shows a hidden or bidirectional Unicode warning:

1. Check whether the warning is in an editable PR body, a review comment, a diff, or a historical immutable commit.
2. If it is in an editable body, rewrite the body with a UTF-8 body file and re-read it through `gh pr view`.
3. If it is in a comment you own and the API can edit it safely, edit it; otherwise add a clean follow-up comment.
4. If it is historical or immutable, document the clean maintained source and do not rewrite history.

## Commit Subjects

- New commit subjects should describe the change, not the PR number.
- Do not rewrite old commits only to remove auto-linked PR numbers.
- GitHub's native PR number display is normal UI and is not a cleanup target.

## Non-Claims

Text hygiene does not claim production readiness, shipping completion, official cloud completion, hybrid completion, persistent memory completion, Google login completion, Discord gateway completion, Tools/MCP completion, provider ecosystem completion, or `src/cogs/ora.py` resolution.
