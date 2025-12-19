"""Logging configuration helpers."""

from __future__ import annotations

import logging
import time
from logging.config import dictConfig
from typing import Any, Dict


class ISO8601UTCFormatter(logging.Formatter):
    """Formatter that outputs timestamps in ISO-8601 UTC."""

    converter = time.gmtime

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:  # noqa: N802
        formatted = super().formatTime(record, datefmt=datefmt)
        if record.msecs:
            return f"{formatted}.{int(record.msecs):03d}Z"
        return f"{formatted}Z"


def setup_logging(level: str) -> None:
    """Configure application logging."""

    config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "structured": {
                "()": ISO8601UTCFormatter,
                "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "structured",
                "level": level,
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "structured",
                "level": level,
                "filename": "logs/ora.log",
                "maxBytes": 5 * 1024 * 1024,  # 5 MB
                "backupCount": 3,
                "encoding": "utf-8",
            }
        },
        "root": {
            "handlers": ["console", "file"],
            "level": level,
        },
    }

    dictConfig(config)
