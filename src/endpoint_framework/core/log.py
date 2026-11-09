"""Structured logging: JSON-lines to a file (evidence trail) + Rich console for humans."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from rich.logging import RichHandler

LOGGER_NAME = "endpoint_framework"
_STD_ATTRS = set(vars(logging.makeLogRecord({})))


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # anything passed via extra={...} becomes a structured field
        entry.update({k: v for k, v in vars(record).items() if k not in _STD_ATTRS})
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def setup_logging(level: str, log_file: Path | None, verbose: bool = False) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    for h in list(logger.handlers):
        logger.removeHandler(h)
        h.close()
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    console = RichHandler(show_path=False, markup=False)
    console.setLevel(logging.DEBUG if verbose else logging.WARNING)
    logger.addHandler(console)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(JsonFormatter())
        logger.addHandler(fh)
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    return logging.getLogger(LOGGER_NAME if name is None else f"{LOGGER_NAME}.{name}")
