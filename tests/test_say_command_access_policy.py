import ast
from pathlib import Path
from types import SimpleNamespace

from src.utils.access_control import can_use_say_command


def test_say_command_policy_rejects_non_owner() -> None:
    bot = SimpleNamespace(config=SimpleNamespace(admin_user_id=12345))

    assert can_use_say_command(bot, 99999) is False


def test_say_command_policy_allows_owner() -> None:
    bot = SimpleNamespace(config=SimpleNamespace(admin_user_id=12345))

    assert can_use_say_command(bot, 12345) is True


def test_say_command_policy_denies_missing_identity() -> None:
    bot = SimpleNamespace(config=SimpleNamespace(admin_user_id=12345))

    assert can_use_say_command(bot, None) is False


def test_say_command_implementation_uses_policy_without_channel_send() -> None:
    source_path = Path("src/cogs/core.py")
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    say_nodes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "say"
    ]
    assert len(say_nodes) == 1
    say_source = ast.get_source_segment(source, say_nodes[0]) or ""

    assert "can_use_say_command" in say_source
    assert "interaction.channel.send" not in say_source
