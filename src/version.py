import os
from pathlib import Path

def get_version():
    version_file = Path(__file__).parent.parent / "VERSION"
    if version_file.exists():
        return version_file.read_text().strip()
    return "unknown"

__version__ = get_version()
