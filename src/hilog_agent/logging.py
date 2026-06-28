"""Centralized logging setup for the Hilog Agent.

Call `setup_logging(verbose=False)` once at startup (CLI or server entry point).
All other modules use `logging.getLogger(__name__)` to get their logger.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

LOG_FORMAT = "%(asctime)s [%(levelname)-5s] %(name)s | %(message)s"
LOG_FORMAT_VERBOSE = "%(asctime)s [%(levelname)-5s] %(name)s:%(lineno)d | %(message)s"
DATE_FORMAT = "%H:%M:%S"


def setup_logging(verbose: bool = False, log_file: str | Path | None = None) -> None:
    """Configure root logger with console and optional file handler.

    Args:
        verbose: If True, set hilog_agent loggers to DEBUG and include line numbers.
        log_file: Path to a log file. If None, defaults to 'hilog_agent.log' in CWD.
    """
    root = logging.getLogger()
    root.setLevel(logging.WARNING)  # suppress noisy third-party logs

    fmt = LOG_FORMAT_VERBOSE if verbose else LOG_FORMAT
    formatter = logging.Formatter(fmt, datefmt=DATE_FORMAT)

    # Our package logger
    pkg = logging.getLogger("hilog_agent")
    pkg.setLevel(logging.DEBUG if verbose else logging.INFO)
    pkg.handlers.clear()
    pkg.propagate = False

    # Console handler (stderr)
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    pkg.addHandler(console)

    # File handler (persistent)
    if log_file is None:
        log_file = Path("hilog_agent.log")
    else:
        log_file = Path(log_file)
    try:
        fh = logging.FileHandler(str(log_file), encoding="utf-8", mode="a")
        fh.setFormatter(logging.Formatter(LOG_FORMAT_VERBOSE, datefmt=DATE_FORMAT))
        fh.setLevel(logging.DEBUG)  # always debug-level to file
        pkg.addHandler(fh)
        pkg.debug("logging initialized — log file: %s", log_file)
    except OSError as e:
        pkg.warning("could not create log file: %s", e)

    # Also capture uvicorn logs at warning+
    logging.getLogger("uvicorn").setLevel(logging.WARNING)

    pkg.info("logging initialized (verbose=%s)", verbose)
