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


@pytest.fixture
def window(qtbot: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[MainWindow]:
    monkeypatch.setattr(main_window_module, "load_settings", lambda: UserSettings())
    monkeypatch.setattr(main_window_module, "save_settings", lambda _settings: tmp_path)
    result = MainWindow(QtWidgets, QtCore, QtGui)
    qtbot.addWidget(result.window)
    result.show()
    yield result
    if result.worker is not None:
        result.worker.cancel()
    if result.thread is not None:
        qtbot.waitUntil(lambda: result.thread is None, timeout=15_000)
    result.window.close()


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
    window: MainWindow, qtbot: Any
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


def test_close_during_analysis_cancels_then_closes(window: MainWindow, qtbot: Any) -> None:
    window.players.setValue(10)
    window.preset_combo.setCurrentText("Very Accurate")
    window.analyze()
    qtbot.waitUntil(lambda: window.thread is not None and window.thread.isRunning(), timeout=2_000)

    window.window.close()
    qtbot.waitUntil(lambda: window.thread is None, timeout=15_000)
    qtbot.waitUntil(lambda: not window.window.isVisible(), timeout=2_000)


def test_theme_resources_and_empty_states_are_visible(window: MainWindow) -> None:
    window._apply_theme("dark")
    assert "#202326" in window.window.styleSheet()
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
