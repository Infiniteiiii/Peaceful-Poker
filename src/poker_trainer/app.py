"""Minimal PySide6 application shell for the current development stage."""

import sys


def run() -> int:
    """Start the desktop application shell."""
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication, QLabel, QMainWindow
    except ImportError as exc:  # pragma: no cover - depends on optional local install state
        raise RuntimeError(
            "PySide6 is required to run the application shell. "
            "Install dependencies with `python -m pip install -e .[dev]`."
        ) from exc

    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle("Poker Decision Trainer")

    label = QLabel(
        "Poker Decision Trainer\n\nDevelopment build: card, deck, and hand evaluator stage."
    )
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setMinimumSize(640, 360)

    window.setCentralWidget(label)
    window.resize(900, 600)
    window.show()
    return app.exec()
