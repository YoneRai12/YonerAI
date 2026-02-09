from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "scripts" / "templates" / "skill"
SKILLS_DIR = ROOT / "src" / "skills"


def _sanitize_name(raw: str) -> str:
    s = (raw or "").strip()
    s = s.replace(" ", "_").replace("-", "_")
    s = re.sub(r"[^a-zA-Z0-9_]", "", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        raise SystemExit("Invalid skill name.")
    if s.lower() in {"template", "__pycache__"}:
        raise SystemExit("Reserved skill name.")
    return s


def _render(text: str, *, skill_name: str) -> str:
    return text.replace("{{SKILL_NAME}}", skill_name)


def main() -> None:
    ap = argparse.ArgumentParser(description="Create a new YonerAI skill scaffold.")
    ap.add_argument("name", help="Skill name (folder + tool name). Example: my_skill")
    args = ap.parse_args()

    name = _sanitize_name(args.name)
    out_dir = SKILLS_DIR / name
    if out_dir.exists():
        raise SystemExit(f"Skill already exists: {out_dir}")

    if not TEMPLATE_DIR.exists():
        raise SystemExit(f"Template missing: {TEMPLATE_DIR}")

    out_dir.mkdir(parents=True, exist_ok=False)
    for rel in ["SKILL.md", "tool.py", "schema.json"]:
        src = TEMPLATE_DIR / rel
        dst = out_dir / rel
        raw = src.read_text(encoding="utf-8")
        dst.write_text(_render(raw, skill_name=name) + ("" if raw.endswith("\n") else "\n"), encoding="utf-8")

    print(f"Created: {out_dir}")


if __name__ == "__main__":
    main()

