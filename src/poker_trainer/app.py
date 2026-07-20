"""PySide6 application entry for Peaceful Poker."""

import json
import os
import sys
from pathlib import Path
from typing import Any

from poker_trainer.services.logging_service import configure_logging


def smoke_test_enabled() -> bool:
    """Return whether explicit application smoke behavior is enabled."""
    return os.environ.get("PEACEFUL_POKER_SMOKE_TEST") == "1"


def run() -> int:
    """Start the desktop application."""
    frozen = bool(getattr(sys, "frozen", False))
    source_plugin_root: Path | None = None
    try:
        import PySide6

        if not frozen:
            pyside_root = Path(PySide6.__file__).resolve().parent
            source_plugin_root = pyside_root / "plugins"
            platform_plugins = source_plugin_root / "platforms"

            if source_plugin_root.is_dir():
                os.environ["QT_PLUGIN_PATH"] = str(source_plugin_root)

            if platform_plugins.is_dir():
                os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(platform_plugins)

        from PySide6 import QtCore, QtGui, QtWidgets
    except ImportError as exc:  # pragma: no cover - depends on optional local install state
        raise RuntimeError(
            "PySide6 is required to run Peaceful Poker. "
            "Install dependencies with `python -m pip install -e .[dev]`."
        ) from exc

    from poker_trainer.resource_path import validate_required_resources
    from poker_trainer.ui.main_window import MainWindow, _terminology_entries

    resources = validate_required_resources()
    log_path = configure_logging()

    if source_plugin_root is not None and source_plugin_root.is_dir():
        QtCore.QCoreApplication.setLibraryPaths([str(source_plugin_root)])

    app: Any = QtWidgets.QApplication.instance()

    if app is None:
        app = QtWidgets.QApplication(sys.argv)

    app.setApplicationName("Peaceful Poker")
    app.setApplicationDisplayName("Peaceful Poker")
    app.setApplicationVersion("1.1.0")

    app.setWindowIcon(QtGui.QIcon(str(resources["Logo.png"])))

    main_window = MainWindow(QtWidgets, QtCore, QtGui)
    app._peaceful_poker_main_window = main_window
    main_window.show()

    # Start hot-reload watcher if enabled (development only)
    observer = None

    if os.environ.get("PEACEFUL_POKER_HOT_RELOAD") == "1":
        try:
            from poker_trainer.services.hot_reload_service import (
                start_hot_reload_watcher,
            )

            ui_dir = Path(__file__).parent / "ui"
            observer = start_hot_reload_watcher(
                lambda: main_window.reload_ui(),
                ui_dir,
            )
        except ImportError:
            print("[HOT RELOAD] watchdog not installed; skipping hot-reload")

    smoke_enabled = smoke_test_enabled()
    smoke_report = os.environ.get("PEACEFUL_POKER_SMOKE_REPORT") if smoke_enabled else None
    smoke_payload: dict[str, object] = {}

    if smoke_report:
        from poker_trainer.services.export_service import (
            export_analysis_json,
            export_analysis_markdown,
        )
        from poker_trainer.services.settings_service import save_settings, settings_path
        from poker_trainer.services.storage_service import (
            SavedHand,
            load_hand,
            save_hand,
            user_data_dir,
        )

        data_dir = user_data_dir()
        settings_existed_at_start = settings_path().is_file()

        def start_smoke() -> None:
            try:
                smoke_payload.update(
                    {
                        "executable_launched": main_window.window.isVisible(),
                        "landing_page_loaded": main_window._landing_page.isVisible(),
                        "frozen": frozen,
                    }
                )
                main_window._show_main_area()
                main_window._apply_theme("dark")
                dark_theme_loaded = bool(main_window.window.styleSheet().strip())
                main_window._apply_theme("light")
                smoke_payload["themes_loaded"] = dark_theme_loaded and bool(
                    main_window.window.styleSheet().strip()
                )

                main_window.preset_combo.setCurrentText("Quick")
                for edit, value in zip(
                    main_window.card_edits,
                    ("AS", "KS", "QS", "10D", "4S"),
                    strict=False,
                ):
                    edit.setText(value)
                main_window.analyze()
            except Exception as exc:  # noqa: BLE001 - release smoke boundary
                smoke_payload["smoke_error"] = str(exc)
                main_window.window.close()

        def finish_smoke() -> None:
            if main_window.thread is not None:
                QtCore.QTimer.singleShot(100, finish_smoke)
                return
            try:
                result = main_window.latest_result
                smoke_payload.update(
                    {
                        "analysis_complete": result is not None,
                        "action_aware_complete": (
                            result is not None and result.action_aware is not None
                        ),
                        "resources_loaded": all(path.is_file() for path in resources.values()),
                        "resource_count": len(resources),
                        "window_title": main_window.window.windowTitle(),
                        "user_data_dir": str(data_dir),
                        "log_file": str(log_path),
                        "output": main_window.output.toPlainText(),
                    }
                )
                if result is None:
                    raise RuntimeError("Packaged analysis did not produce a result.")

                saved = save_hand(
                    SavedHand(
                        result.game_state,
                        str(main_window.range_combo.currentText()),
                    )
                )
                loaded = load_hand(saved)
                settings_file = save_settings(main_window.settings)
                export_dir = data_dir / "exports"
                export_dir.mkdir(parents=True, exist_ok=True)
                markdown_export = export_analysis_markdown(result, export_dir / "smoke-analysis.md")
                json_export = export_analysis_json(result, export_dir / "smoke-analysis.json")

                main_window.about()
                app.processEvents()
                help_dialog = main_window.help_dialog
                terminology_pages = (
                    help_dialog.findChildren(QtWidgets.QWidget, "terminologyPage")
                    if help_dialog is not None
                    else []
                )
                terminology_scrolls = (
                    help_dialog.findChildren(QtWidgets.QScrollArea, "terminologyScrollArea")
                    if help_dialog is not None
                    else []
                )
                terminology_cards = (
                    help_dialog.findChildren(QtWidgets.QFrame, "terminologyCard")
                    if help_dialog is not None
                    else []
                )
                expected_terms = len(_terminology_entries())
                terminology_single_layout = (
                    len(terminology_pages) == 1
                    and len(terminology_scrolls) == 1
                    and len(terminology_cards) == expected_terms
                    and len({id(card) for card in terminology_cards}) == expected_terms
                )
                if help_dialog is not None:
                    help_dialog.close()
                    app.processEvents()

                action_labels = (
                    [item.candidate.label for item in result.action_aware.action_results]
                    if result.action_aware is not None
                    else []
                )
                labels_are_contextual = bool(action_labels) and all(
                    "Bet to" not in label and label != "All-in" for label in action_labels
                )

                main_window.training()
                training_started = (
                    main_window.training_state is not None
                    and bool(main_window.training_choices.buttons())
                    and main_window.training_panel.isVisible()
                )
                smoke_payload.update(
                    {
                        "saved_hand": str(saved),
                        "save_round_trip": loaded.game_state == result.game_state,
                        "settings_file": str(settings_file),
                        "settings_writable": settings_file.is_file(),
                        "settings_existed_at_start": settings_existed_at_start,
                        "markdown_export": str(markdown_export),
                        "json_export": str(json_export),
                        "exports_written": markdown_export.is_file() and json_export.is_file(),
                        "terminology_loaded": expected_terms > 0,
                        "terminology_count": expected_terms,
                        "terminology_single_layout": terminology_single_layout,
                        "training_started": training_started,
                        "action_labels_contextual": labels_are_contextual,
                        "street": result.game_state.street.value,
                        "current_hand": result.current_hand.description,
                        "equity": result.equity.total_equity,
                        "recommendation": result.recommendation.primary_action,
                        "action_aware_recommendation": (
                            result.action_aware.recommended_action if result.action_aware else None
                        ),
                    }
                )
            except Exception as exc:  # noqa: BLE001 - release smoke boundary
                smoke_payload["smoke_error"] = str(exc)
            finally:
                main_window.window.close()

        QtCore.QTimer.singleShot(0, start_smoke)
        QtCore.QTimer.singleShot(100, finish_smoke)

    autoclose = os.environ.get("PEACEFUL_POKER_AUTOCLOSE_MS") if smoke_enabled else None

    if autoclose:
        QtCore.QTimer.singleShot(
            int(autoclose),
            main_window.window.close,
        )

    result = int(app.exec())

    # Stop observer on exit
    if observer is not None:
        observer.stop()
        observer.join()

    if smoke_report:
        smoke_payload["clean_close"] = (
            result == 0 and main_window.thread is None and not main_window.window.isVisible()
        )
        report_path = Path(smoke_report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(smoke_payload, indent=2), encoding="utf-8")

    return result


if __name__ == "__main__":
    raise SystemExit(run())
