"""PyQt shell window — loads the chat UI in QWebEngineView."""

from __future__ import annotations

import os
import sys

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QAction
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget

HOST = os.environ.get("HILOG_HOST", "127.0.0.1")
PORT = os.environ.get("HILOG_PORT", "8710")
BASE_URL = f"http://{HOST}:{PORT}"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Hilog Agent")
        self.resize(1200, 800)
        self.setMinimumSize(900, 600)

        # Web view
        self.web = QWebEngineView()
        self.web.setUrl(QUrl(BASE_URL))

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.web)
        self.setCentralWidget(central)

        # Menu
        menu = self.menuBar()
        file_menu = menu.addMenu("&File")
        reload_action = QAction("&Reload", self)
        reload_action.triggered.connect(self.web.reload)
        file_menu.addAction(reload_action)
        file_menu.addSeparator()
        quit_action = QAction("&Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

    def closeEvent(self, event):  # noqa: N802 (Qt override)
        self.web.page().deleteLater()
        super().closeEvent(event)


def run_pyqt() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Hilog Agent")
    app.setOrganizationName("hilog-agent")

    window = MainWindow()
    window.show()
    return app.exec()
