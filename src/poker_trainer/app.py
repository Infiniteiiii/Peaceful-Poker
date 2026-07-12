"""PySide6 application entry for Peaceful Poker."""

import os
import sys

from poker_trainer.services.logging_service import configure_logging


def run() -> int:
    """Start the desktop application."""
    try:
        from PySide6 import QtCore, QtWidgets
    except ImportError as exc:  # pragma: no cover - depends on optional local install state
        raise RuntimeError(
            "PySide6 is required to run Peaceful Poker. "
            "Install dependencies with `python -m pip install -e .[dev]`."
        ) from exc

    from poker_trainer.ui.main_window import MainWindow

    configure_logging()
    app = QtWidgets.QApplication(sys.argv)
    main_window = MainWindow(QtWidgets, QtCore)
    main_window.show()
    autoclose = os.environ.get("PEACEFUL_POKER_AUTOCLOSE_MS")
    if autoclose:
        QtCore.QTimer.singleShot(int(autoclose), app.quit)
    return int(app.exec())
