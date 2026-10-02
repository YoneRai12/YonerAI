from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from yonerai_cli.config import ConfigError, build_config_report, default_config_path, load_cli_config, set_cli_config_value


class ConfigServiceError(Exception):
    pass


def build_config_status_report(args: argparse.Namespace) -> dict[str, Any]:
    try:
        config = load_cli_config(args.config_path)
        config_path = Path(args.config_path).expanduser() if args.config_path else default_config_path()
        return build_config_report(config, exists=config_path.exists())
    except ConfigError as exc:
        raise ConfigServiceError(str(exc)) from exc


def set_config_status_report(args: argparse.Namespace) -> dict[str, Any]:
    try:
        config = set_cli_config_value(args.config_key, args.config_value, args.config_path)
        return build_config_report(config, exists=True) | {
            "operation": "set",
            "changed_key": args.config_key,
        }
    except ConfigError as exc:
        raise ConfigServiceError(str(exc)) from exc
