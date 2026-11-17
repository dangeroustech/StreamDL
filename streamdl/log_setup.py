"""Logging: full logs to a file, stdout or both, plus a stdout-only progress summary.

Destinations (LOG_DEST / -log-dest):
  file   full logs to <data>/streamdl.log; stdout only gets the Active Downloads
         block each round (the v3 default)
  stdout full logs to stdout
  both   full logs to the file and stdout
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TextIO

LOGGER_NAME = "streamdl"
_FORMAT = "[%(asctime)s] %(levelname)s %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"
_LEVELS = {
    "trace": logging.DEBUG,
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warn": logging.WARNING,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "fatal": logging.CRITICAL,
    "panic": logging.CRITICAL,
}

# Receives the per-round Active Downloads block when full logs go only to a file.
console_summary: TextIO | None = None


class LogDest(StrEnum):
    FILE = "file"
    STDOUT = "stdout"
    BOTH = "both"


_DEST_ALIASES = {
    "": LogDest.FILE,
    "file": LogDest.FILE,
    "stdout": LogDest.STDOUT,
    "console": LogDest.STDOUT,
    "container": LogDest.STDOUT,
    "both": LogDest.BOTH,
    "all": LogDest.BOTH,
}


def parse_log_dest(value: str) -> LogDest:
    try:
        return _DEST_ALIASES[value.strip().lower()]
    except KeyError:
        raise ValueError(
            f"invalid log destination {value!r} (want file, stdout, or both)"
        ) from None


def parse_level(value: str) -> int:
    """Map a logrus-style level name to a logging level; unknown names mean INFO."""
    return _LEVELS.get(value.strip().lower(), logging.INFO)


@dataclass
class LoggingConfig:
    dest: LogDest
    file_path: str
    handlers: list[logging.Handler] = field(default_factory=list)

    def close(self) -> None:
        global console_summary
        logger = logging.getLogger(LOGGER_NAME)
        for handler in self.handlers:
            logger.removeHandler(handler)
            handler.close()
        self.handlers.clear()
        console_summary = None


def setup_logging(
    level: str, dest: str, file_path: str, data_dir: str
) -> LoggingConfig:
    """Configure the 'streamdl' logger; raises ValueError or OSError on bad input."""
    global console_summary
    log_dest = parse_log_dest(dest)
    file_path = file_path.strip()
    if log_dest is not LogDest.STDOUT and not file_path:
        file_path = os.path.join(data_dir.strip() or "/app/data", "streamdl.log")

    handlers: list[logging.Handler] = []
    console_summary = None
    if log_dest is LogDest.STDOUT:
        handlers.append(logging.StreamHandler(sys.stdout))
    else:
        os.makedirs(os.path.dirname(file_path) or ".", mode=0o755, exist_ok=True)
        handlers.append(logging.FileHandler(file_path, encoding="utf-8"))
        if log_dest is LogDest.BOTH:
            handlers.append(logging.StreamHandler(sys.stdout))
        else:
            console_summary = sys.stdout

    formatter = logging.Formatter(_FORMAT, _DATEFMT)
    logger = logging.getLogger(LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    for handler in handlers:
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(parse_level(level))
    return LoggingConfig(log_dest, file_path, handlers)


def write_console(text: str) -> None:
    """Write text to the console summary sink, if one is active."""
    if console_summary is None:
        return
    console_summary.write(text)
    console_summary.flush()
