"""Centralized logging setup for the Hilog Agent.

Call `setup_logging(verbose=False)` once at startup (CLI or server entry point).
All other modules use `logging.getLogger(__name__)` to get their logger.
"""

from __future__ import annotations

import logging
import sys

LOG_FORMAT = "%(asctime)s [%(levelname)-5s] %(name)s | %(message)s"
LOG_FORMAT_VERBOSE = "%(asctime)s [%(levelname)-5s] %(name)s:%(lineno)d | %(message)s"
DATE_FORMAT = "%H:%M:%S"


def setup_logging(verbose: bool = False) -> None:
    """Configure root logger and console handler.

    Args:
        verbose: If True, set hilog_agent loggers to DEBUG and include line numbers.
    """
    root = logging.getLogger()
    root.setLevel(logging.WARNING)  # suppress noisy third-party logs

    fmt = LOG_FORMAT_VERBOSE if verbose else LOG_FORMAT
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(fmt, datefmt=DATE_FORMAT))

    # Our package logger
    pkg = logging.getLogger("hilog_agent")
    pkg.setLevel(logging.DEBUG if verbose else logging.INFO)
    pkg.handlers.clear()
    pkg.addHandler(handler)
    pkg.propagate = False

    # Also capture uvicorn logs at warning+
    logging.getLogger("uvicorn").setLevel(logging.WARNING)

    pkg.info("logging initialized (verbose=%s)", verbose)
