"""YonerAI local CLI runtime."""

from importlib import metadata
from pathlib import Path
import re
import tomllib

__all__ = ["__version__"]

_PACKAGE_NAME = "yonerai-cli"
_PACKAGE_VERSION_FALLBACK = "0.5.0"
_PEP440_PRERELEASE_RE = re.compile(r"^(\d+\.\d+\.\d+)(a|b|rc)(\d+)$")
_PEP440_LABELS = {"a": "alpha", "b": "beta", "rc": "rc"}


def _load_package_version() -> str:
    source_version = _load_source_pyproject_version()
    if source_version:
        return source_version
    try:
        return _to_public_semver(metadata.version(_PACKAGE_NAME))
    except metadata.PackageNotFoundError:
        return _to_public_semver(_PACKAGE_VERSION_FALLBACK)


def _load_source_pyproject_version() -> str:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    if not pyproject_path.exists():
        return ""
    try:
        pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    version = str(pyproject.get("project", {}).get("version", "")).strip()
    return _to_public_semver(version) if version else ""


def _to_public_semver(value: str) -> str:
    match = _PEP440_PRERELEASE_RE.fullmatch(value)
    if not match:
        return value
    base, label, number = match.groups()
    return f"{base}-{_PEP440_LABELS[label]}.{number}"


__version__ = _load_package_version()
