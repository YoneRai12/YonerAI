from __future__ import annotations


def split_discord_message_chunks(
    content: str,
    *,
    header: str = "",
    max_single_message: int = 2000,
    chunk_size: int = 1900,
) -> tuple[str, ...]:
    """Split legacy ORA Discord replies without importing Discord runtime."""
    if max_single_message < 1:
        raise ValueError("max_single_message must be positive")
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive")

    full_text = header + content
    if len(full_text) <= max_single_message:
        return (full_text,)
    return tuple(full_text[index : index + chunk_size] for index in range(0, len(full_text), chunk_size))


def message_format_helper_status() -> dict[str, object]:
    sample = split_discord_message_chunks("a" * 3890, header="head: ")
    return {
        "name": "ora_message_format_helper",
        "source": "src/cogs/ora_message_format_helpers.py",
        "status": "ok" if [len(chunk) for chunk in sample] == [1900, 1900, 96] else "unavailable",
        "available": [len(chunk) for chunk in sample] == [1900, 1900, 96],
        "discord_runtime_imported": False,
        "broad_ora_refactor": False,
    }


__all__ = [
    "message_format_helper_status",
    "split_discord_message_chunks",
]
