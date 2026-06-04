from __future__ import annotations

from yonerai_cli.tui.keymap import JAPANESE_SLASH_ALIASES, SLASH_COMMANDS


def slash_command_summary(lang: str) -> str:
    lines = ["候補:" if lang == "ja" else "Suggestions:"]
    for spec in SLASH_COMMANDS:
        if lang == "ja":
            aliases = ", ".join(alias for alias in JAPANESE_SLASH_ALIASES.get(spec.canonical, ()) if alias != spec.command)
            alias_text = f" / {aliases}" if aliases else ""
            lines.append(f"  {spec.command:<10} {spec.description_ja}{alias_text}")
        else:
            primary = spec.aliases[0] if spec.aliases else spec.command
            lines.append(f"  {primary:<10} {spec.description_en}")
    lines.append("")
    return "\n".join(lines)
