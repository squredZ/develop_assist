"""Application launcher — starts FastAPI server then PyQt GUI.

Usage:
    python -m frontend.main        (dev)
    hilog-gui                      (after pip install)

Environment:
    HILOG_HOST  — bind host (default: 127.0.0.1)
    HILOG_PORT  — bind port  (default: 8710)
"""

from __future__ import annotations

import os
import sys
import threading
import time

import uvicorn

HOST = os.environ.get("HILOG_HOST", "127.0.0.1")
PORT = int(os.environ.get("HILOG_PORT", "8710"))


def _run_server() -> None:
    """Run FastAPI via uvicorn in this thread (blocking)."""
    uvicorn.run(
        "hilog_agent.server:app",
        host=HOST,
        port=PORT,
        log_level="warning",
        access_log=False,
    )


def main() -> int:
    """Start server thread, launch PyQt, wait for exit."""
    # Start FastAPI in daemon thread
    server_thread = threading.Thread(target=_run_server, daemon=True)
    server_thread.start()

    # Wait for server to be ready
    for _ in range(50):  # 5 seconds max
        try:
            import urllib.request

            urllib.request.urlopen(f"http://{HOST}:{PORT}/api/features", timeout=0.1)
            break
        except Exception:
            time.sleep(0.1)

    # Launch PyQt
    from frontend.app import run_pyqt

    return run_pyqt()


if __name__ == "__main__":
    sys.exit(main())
