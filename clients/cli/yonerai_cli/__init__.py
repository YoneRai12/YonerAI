"""YonerAI local CLI runtime alpha."""

from importlib import metadata
import re

__all__ = ["__version__"]

_PACKAGE_NAME = "yonerai-cli"
_PACKAGE_VERSION_FALLBACK = "0.3.0a1"
_PEP440_PRERELEASE_RE = re.compile(r"^(\d+\.\d+\.\d+)(a|b|rc)(\d+)$")
_PEP440_LABELS = {"a": "alpha", "b": "beta", "rc": "rc"}


def _load_package_version() -> str:
    try:
        return _to_public_semver(metadata.version(_PACKAGE_NAME))
    except metadata.PackageNotFoundError:
        return _to_public_semver(_PACKAGE_VERSION_FALLBACK)


def _to_public_semver(value: str) -> str:
    match = _PEP440_PRERELEASE_RE.fullmatch(value)
    if not match:
        return value
    base, label, number = match.groups()
    return f"{base}-{_PEP440_LABELS[label]}.{number}"


__version__ = _load_package_version()
