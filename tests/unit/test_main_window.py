"""Headless integration tests for the release desktop window."""

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from PySide6 import QtCore, QtGui, QtWidgets

from poker_trainer.models import Card, GameState, OpponentProfile, Position
from poker_trainer.services.settings_service import UserSettings
from poker_trainer.ui import main_window as main_window_module
from poker_trainer.ui.main_window import MainWindow
from poker_trainer.utils.exceptions import DuplicateCardError


def cards(codes: str) -> tuple[Card, ...]:
    return tuple(Card.from_code(code) for code in codes.split())


def enter_default_cards(window: MainWindow) -> None:
    for edit, value in zip(
        window.card_edits,
        ("AS", "KS", "QS", "10D", "4S"),
        strict=False,
    ):
        edit.setText(value)


@pytest.fixture
def window(
    qapp: Any,
    qtbot: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Iterator[MainWindow]:
    monkeypatch.setattr(main_window_module, "load_settings", lambda: UserSettings())
    monkeypatch.setattr(main_window_module, "save_settings", lambda _settings: tmp_path)
    assert QtWidgets.QApplication.instance() is qapp
    result = MainWindow(QtWidgets, QtCore, QtGui)
    qtbot.addWidget(result.window)
    result.show()
    enter_default_cards(result)
    yield result
    if result.thread is not None and result.thread.isRunning() and result.worker is not None:
        result.worker.cancel()
    if result.thread is not None:
        qtbot.waitUntil(lambda: result.thread is None, timeout=15_000)
    result.window.close()
    qtbot.waitUntil(lambda: not result.window.isVisible(), timeout=2_000)


def test_startup_remains_visible_idle_and_empty(
    qapp: Any, qtbot: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        main_window_module,
        "load_settings",
        lambda: UserSettings(automatic_analysis=True),
    )
    monkeypatch.setattr(main_window_module, "save_settings", lambda _settings: tmp_path)
    result = MainWindow(QtWidgets, QtCore, QtGui)
    qtbot.addWidget(result.window)
    result.show()
    result._schedule_automatic_analysis()

    assert QtWidgets.QApplication.instance() is qapp
    assert result.window.isVisible()
    assert all(not edit.text() for edit in result.card_edits)
    assert result.thread is None
    assert result.worker is None
    assert not result._auto_timer.isActive()

    result.window.close()


def test_repeated_window_creation_and_close_uses_one_application(
    qapp: Any,
    qtbot: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(main_window_module, "load_settings", lambda: UserSettings())
    monkeypatch.setattr(main_window_module, "save_settings", lambda _settings: tmp_path)

    for _ in range(8):
        result = MainWindow(QtWidgets, QtCore, QtGui)
        qtbot.addWidget(result.window)
        result.show()
        qtbot.waitUntil(result.window.isVisible, timeout=2_000)
        assert QtWidgets.QApplication.instance() is qapp
        assert result.thread is None

        concrete_window = result.window
        concrete_window.close()
        qtbot.waitUntil(
            lambda window=concrete_window: not window.isVisible(),
            timeout=2_000,
        )

    assert QtWidgets.QApplication.instance() is qapp
    assert not qapp.closingDown()


def test_card_entry_rejects_incomplete_board_and_duplicates(window: MainWindow) -> None:
    window.card_edits[3].clear()
    with pytest.raises(ValueError, match="all three flop cards"):
        window._state()

    window.card_edits[3].setText("10D")
    window.card_edits[4].setText("AS")
    with pytest.raises(DuplicateCardError):
        window._state()


def test_clear_street_removes_only_latest_street(window: MainWindow) -> None:
    state = GameState(
        active_players=2,
        hero_cards=cards("AS KS"),
        community_cards=cards("QS 10D 4S 2C 3H"),
        hero_position=Position.BUTTON,
    )
    window._apply_state(state)

    window.clear_current_street()
    assert [edit.text() for edit in window.card_edits[2:]] == ["QS", "10D", "4S", "2C", ""]

    window.clear_current_street()
    assert [edit.text() for edit in window.card_edits[2:]] == ["QS", "10D", "4S", "", ""]


def test_background_analysis_completes_and_populates_results(
    window: MainWindow, qapp: Any, qtbot: Any
) -> None:
    state = GameState(
        active_players=2,
        hero_cards=cards("AS KS"),
        community_cards=cards("QS JS 10S 2D 3C"),
        hero_position=Position.BUTTON,
        hero_stack=500,
    )
    window._apply_state(state)
    window.analyze()
    qtbot.waitUntil(lambda: window.thread is None, timeout=15_000)

    assert window.latest_result is not None
    assert "Royal Flush" in window.output.toPlainText()
    assert window.latest_result.action_aware is not None
    assert "RAW SHOWDOWN ANALYSIS" in window.output.toPlainText()
    assert "ACTION-AWARE ANALYSIS" in window.output.toPlainText()
    assert window.action_table.rowCount() > 0
    assert window.export_button.isEnabled()
    assert window.window.isVisible()
    assert window.thread is None
    assert window.worker is None
    assert QtWidgets.QApplication.instance() is qapp
    assert not qapp.closingDown()


def test_failed_analysis_displays_error_and_leaves_window_open(
    window: MainWindow, qapp: Any, qtbot: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FailingAnalysisWorker:
        def __init__(self, qtcore: Any, *_args: object, **_kwargs: object) -> None:
            class Worker(qtcore.QObject):
                progress = qtcore.Signal(int, int)
                finished = qtcore.Signal(object)
                error = qtcore.Signal(str)

                @qtcore.Slot()
                def run(self) -> None:
                    self.error.emit("forced analysis failure")

                def cancel(self) -> None:
                    pass

            self.object = Worker()

    monkeypatch.setattr(main_window_module, "AnalysisWorker", FailingAnalysisWorker)
    window.analyze()
    qtbot.waitUntil(lambda: window.thread is None, timeout=2_000)

    assert "forced analysis failure" in window.output.toPlainText()
    assert window.window.isVisible()
    assert QtWidgets.QApplication.instance() is qapp
    assert not qapp.closingDown()


def test_input_change_prevents_stale_worker_result(window: MainWindow, qtbot: Any) -> None:
    window.players.setValue(10)
    window.preset_combo.setCurrentText("Very Accurate")
    window.analyze()
    qtbot.waitUntil(lambda: window.thread is not None and window.thread.isRunning(), timeout=2_000)
    window.card_edits[0].setText("AH")
    window.cancel()
    qtbot.waitUntil(lambda: window.thread is None, timeout=15_000)

    assert window.latest_result is None
    assert "Inputs changed" in window.output.toPlainText()
    assert window.window.isVisible()
    assert not window.close_pending
    assert window.thread is None
    assert window.worker is None


def test_close_during_analysis_cancels_then_closes(
    window: MainWindow, qapp: Any, qtbot: Any
) -> None:
    window.players.setValue(10)
    window.preset_combo.setCurrentText("Very Accurate")
    window.analyze()
    qtbot.waitUntil(lambda: window.thread is not None and window.thread.isRunning(), timeout=2_000)

    window.window.close()
    qtbot.waitUntil(lambda: window.thread is None, timeout=15_000)
    qtbot.waitUntil(lambda: not window.window.isVisible(), timeout=2_000)

    assert window.worker is None
    assert QtWidgets.QApplication.instance() is qapp
    assert not qapp.closingDown()


def test_theme_resources_and_empty_states_are_visible(window: MainWindow) -> None:
    window._apply_theme("dark")
    assert "#1C2128" in window.window.styleSheet()
    window.new_hand()
    assert "Enter two hero cards" in window.output.toPlainText()
    assert window.window.minimumWidth() <= 900


def test_table_controls_configure_profiles_folds_calls_and_players_behind(
    window: MainWindow,
) -> None:
    window.position.setCurrentText(Position.SMALL_BLIND.display_name)
    window.players_behind.setValue(3)
    window.folded_seats.setText("3")
    window.called_seats.setText("2")
    window.aggressor_seat.setValue(4)
    window.profile_combo.setCurrentIndex(
        window.profile_combo.findData(OpponentProfile.LOOSE_AGGRESSIVE.value)
    )

    game_state = window._state()

    assert game_state.table_state is not None
    assert game_state.table_state.player(3).folded
    assert "Called" in game_state.table_state.player(2).previous_actions
    assert "Raised" in game_state.table_state.player(4).previous_actions
    assert all(
        player.profile is OpponentProfile.LOOSE_AGGRESSIVE
        for player in game_state.table_state.active_opponents
    )
    assert "Behind hero" in window.action_order_label.text()


def test_individual_opponent_override_and_last_to_act_details(window: MainWindow) -> None:
    base = window._build_table_state("flop")
    opponent = base.active_opponents[0]
    window.player_overrides[opponent.seat] = replace(
        opponent,
        profile=OpponentProfile.NIT,
        range_text="premium",
        stack=50.0,
    )
    configured = window._state()
    assert configured.table_state is not None
    assert configured.table_state.player(opponent.seat).profile is OpponentProfile.NIT
    assert configured.table_state.player(opponent.seat).stack == 50.0

    window.position.setCurrentText(Position.BUTTON.display_name)
    window.players_behind.setValue(0)
    last_to_act = window._state()
    assert last_to_act.table_state is not None
    assert not last_to_act.table_state.players_after_hero()


def test_nonhero_current_actor_is_represented_but_analysis_waits(window: MainWindow) -> None:
    window.current_actor_seat.setValue(2)
    game_state = window._state()

    assert game_state.table_state is not None
    assert game_state.table_state.current_actor_seat == 2
    window.analyze()
    assert "requires Hero to be the current actor" in window.output.toPlainText()
