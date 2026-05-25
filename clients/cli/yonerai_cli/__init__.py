"""YonerAI local CLI runtime alpha."""

from importlib import metadata

__all__ = ["__version__"]

_PACKAGE_NAME = "yonerai-cli"
_PACKAGE_VERSION_FALLBACK = "0.2.0a1"


def _load_package_version() -> str:
    try:
        return metadata.version(_PACKAGE_NAME)
    except metadata.PackageNotFoundError:
        return _PACKAGE_VERSION_FALLBACK


__version__ = _load_package_version()
