import re

_CHANNEL_TAG_PATTERN = re.compile(r"<\|.*?\|>")


def clean_content(text: str) -> str:
    """Remove internal tags like <|channel|> from generated text."""
    cleaned = _CHANNEL_TAG_PATTERN.sub("", text)
    return cleaned.strip()
