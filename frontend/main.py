"""Application launcher — starts FastAPI server then PyQt GUI.

Usage:
    python -m frontend.main        (dev)
    hilog-gui                      (after pip install)

Environment:
    HILOG_HOST   — bind host (default: 127.0.0.1)
    HILOG_PORT   — bind port  (default: 8710)
    HILOG_QUIET  — set to 1 to suppress debug logging
"""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

import uvicorn

HOST = os.environ.get("HILOG_HOST", "127.0.0.1")
PORT = int(os.environ.get("HILOG_PORT", "8710"))

# Write startup log to file early, before any imports that might fail
_STARTUP_LOG: list[str] = []


def _log(msg: str) -> None:
    _STARTUP_LOG.append(msg)
    print(msg, file=sys.stderr)  # also stderr for dev


def _flush_startup_log(log_dir: Path) -> None:
    if _STARTUP_LOG:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            with open(log_dir / "startup.log", "a", encoding="utf-8") as f:
                for line in _STARTUP_LOG:
                    f.write(line + "\n")
        except OSError:
            pass


def _run_server(log_dir: Path) -> None:
    """Run FastAPI via uvicorn in this thread (blocking)."""
    # PyInstaller with console=False sets sys.stdout/stderr to None.
    # Uvicorn's DefaultFormatter needs them for isatty() color detection.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")

    try:
        uvicorn.run(
            "hilog_agent.server:app",
            host=HOST,
            port=PORT,
            log_level="warning",
            access_log=False,
        )
    except Exception as e:
        # Write crash info to a file since daemon threads die silently
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            import traceback
            with open(log_dir / "server_crash.log", "a", encoding="utf-8") as f:
                f.write(f"Server crashed: {e}\n")
                traceback.print_exc(file=f)
        except OSError:
            pass
        raise


def main() -> int:
    """Start server thread, launch PyQt, wait for exit."""
    _log("=== Hilog Agent starting ===")
    _log(f"Host: {HOST}:{PORT}")

    # Detect bundle root for log output
    if hasattr(sys, "_MEIPASS"):
        bundle_root = Path(sys._MEIPASS)
        log_dir = Path(sys.executable).parent  # writable dir next to exe
    else:
        bundle_root = Path(__file__).resolve().parent.parent
        log_dir = bundle_root
    _log(f"Bundle root: {bundle_root}")

    # Start FastAPI in daemon thread
    _log("Starting server thread...")
    server_thread = threading.Thread(target=_run_server, args=(log_dir,), daemon=True)
    server_thread.start()

    # Wait for server to be ready
    _log("Waiting for server to be ready...")
    server_ready = False
    for i in range(50):  # 5 seconds max
        try:
            import urllib.request

            urllib.request.urlopen(f"http://{HOST}:{PORT}/api/features", timeout=0.1)
            server_ready = True
            _log(f"Server ready after {i * 0.1:.1f}s")
            break
        except Exception:
            time.sleep(0.1)

    if not server_ready:
        _log("ERROR: Server failed to start")
        _flush_startup_log(log_dir)
        return 1

    # Launch PyQt
    _log("Launching PyQt GUI...")
    _flush_startup_log(log_dir)
    from frontend.app import run_pyqt

    return run_pyqt()


if __name__ == "__main__":
    sys.exit(main())
