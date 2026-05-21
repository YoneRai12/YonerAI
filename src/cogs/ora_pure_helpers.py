import re


def clean_content(text: str) -> str:
    """Remove internal tags like <|channel|> from generated text."""
    cleaned = re.sub(r"<\|.*?\|>", "", text)
    return cleaned.strip()
