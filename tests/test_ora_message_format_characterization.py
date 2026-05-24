from __future__ import annotations

import ast
import asyncio
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
ORA_SOURCE = REPO_ROOT / "src" / "cogs" / "ora.py"


class _FakeChannel:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, content: str) -> None:
        self.sent.append(content)


class _FakeMessage:
    def __init__(self) -> None:
        self.replies: list[dict[str, Any]] = []
        self.channel = _FakeChannel()

    async def reply(self, content: str, *, files: list[object], mention_author: bool) -> None:
        self.replies.append(
            {
                "content": content,
                "files": files,
                "mention_author": mention_author,
            }
        )


def _build_large_message_fixture() -> object:
    source = ORA_SOURCE.read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    ora_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ORACog")
    method = next(
        node
        for node in ora_class.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_send_large_message"
    )
    module = ast.Module(
        body=[
            ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
            ast.ClassDef(
                name="OraMessageFixture",
                bases=[],
                keywords=[],
                body=[method],
                decorator_list=[],
            ),
        ],
        type_ignores=[],
    )
    ast.fix_missing_locations(module)
    namespace: dict[str, object] = {}
    exec(compile(module, str(ORA_SOURCE), "exec"), namespace)
    return namespace["OraMessageFixture"]()


def test_ora_large_message_short_reply_characterization() -> None:
    helper = _build_large_message_fixture()
    message = _FakeMessage()
    files: list[object] = [object()]

    result = asyncio.run(helper._send_large_message(message, "body", header="head: ", files=files))

    assert result is None
    assert message.replies == [{"content": "head: body", "files": files, "mention_author": False}]
    assert message.channel.sent == []


def test_ora_large_message_chunking_characterization() -> None:
    helper = _build_large_message_fixture()
    message = _FakeMessage()
    content = "a" * 3890

    result = asyncio.run(helper._send_large_message(message, content, header="head: ", files=None))

    sent_chunks = [message.replies[0]["content"], *message.channel.sent]
    assert result == "Tool executed."
    assert [len(chunk) for chunk in sent_chunks] == [1900, 1900, 96]
    assert "".join(sent_chunks) == "head: " + content
    assert message.replies[0]["files"] == []
    assert message.replies[0]["mention_author"] is False
