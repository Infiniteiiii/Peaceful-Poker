"""PySide6 application entry for Peaceful Poker."""

import json
import os
import sys
from pathlib import Path
from typing import Any

from poker_trainer.services.logging_service import configure_logging


def run() -> int:
    """Start the desktop application."""
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
    except ImportError as exc:  # pragma: no cover - depends on optional local install state
        raise RuntimeError(
            "PySide6 is required to run Peaceful Poker. "
            "Install dependencies with `python -m pip install -e .[dev]`."
        ) from exc

    from poker_trainer.resource_path import resource_path
    from poker_trainer.ui.main_window import MainWindow

    configure_logging()
    app: Any = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("Peaceful Poker")
    app.setApplicationDisplayName("Peaceful Poker")
    app.setApplicationVersion("1.0.0")
    icon_path = resource_path("peaceful_poker.ico")
    if icon_path.exists():
        app.setWindowIcon(QtGui.QIcon(str(icon_path)))
    main_window = MainWindow(QtWidgets, QtCore, QtGui)
    main_window.show()
    smoke_report = os.environ.get("PEACEFUL_POKER_SMOKE_REPORT")
    if smoke_report:
        from poker_trainer.services.storage_service import SavedHand, save_hand, user_data_dir

        main_window.preset_combo.setCurrentText("Quick")

        def finish_smoke() -> None:
            if main_window.thread is not None:
                QtCore.QTimer.singleShot(100, finish_smoke)
                return
            result = main_window.latest_result
            payload: dict[str, object] = {
                "analysis_complete": result is not None,
                "action_aware_complete": result is not None and result.action_aware is not None,
                "resources_loaded": all(
                    resource_path(name).exists()
                    for name in ("light.qss", "dark.qss", "peaceful_poker.ico")
                ),
                "window_title": main_window.window.windowTitle(),
                "user_data_dir": str(user_data_dir()),
                "output": main_window.output.toPlainText(),
            }
            if result is not None:
                saved = save_hand(
                    SavedHand(result.game_state, str(main_window.range_combo.currentText()))
                )
                payload.update(
                    {
                        "saved_hand": str(saved),
                        "street": result.game_state.street.value,
                        "current_hand": result.current_hand.description,
                        "equity": result.equity.total_equity,
                        "recommendation": result.recommendation.primary_action,
                        "action_aware_recommendation": (
                            result.action_aware.recommended_action if result.action_aware else None
                        ),
                    }
                )
            report_path = Path(smoke_report)
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            main_window.window.close()

        QtCore.QTimer.singleShot(0, main_window.analyze)
        QtCore.QTimer.singleShot(100, finish_smoke)
    autoclose = os.environ.get("PEACEFUL_POKER_AUTOCLOSE_MS")
    if autoclose:
        QtCore.QTimer.singleShot(int(autoclose), main_window.window.close)
    return int(app.exec())
