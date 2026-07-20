"""Headless integration tests for the release desktop window."""

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from PySide6 import QtCore, QtGui, QtWidgets

from poker_trainer.engine.candidate_actions import generate_candidate_actions
from poker_trainer.models import ActionAwareSettings, Card, GameState, OpponentProfile, Position
from poker_trainer.services.analysis_service import analyze_game_state
from poker_trainer.services.settings_service import UserSettings
from poker_trainer.strategy.action_recommender import recommend_action
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
    assert "Raw Showdown Analysis" in window.output.toPlainText()
    assert "Action-Aware Analysis" in window.output.toPlainText()
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
    window.advanced_mode_toggle.setChecked(True)
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
    window.advanced_mode_toggle.setChecked(True)
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
    window.advanced_mode_toggle.setChecked(True)
    window.current_actor_seat.setValue(2)
    game_state = window._state()

    assert game_state.table_state is not None
    assert game_state.table_state.current_actor_seat == 2
    window.analyze()
    assert "requires Hero to be the current actor" in window.output.toPlainText()


def test_normal_mode_defaults_help_and_advanced_value_preservation(window: MainWindow) -> None:
    window._show_main_area()
    assert not window.advanced_mode_toggle.isChecked()
    assert not window.advanced_opponents.isVisible()
    assert window.normal_defaults_notice.isVisible()
    assert window.settings.advanced_mode is False

    info_buttons = window.window.findChildren(QtWidgets.QToolButton, "infoButton")
    assert len(info_buttons) >= 10
    assert all(button.toolTip() for button in info_buttons)
    assert all(button.accessibleName().startswith("Information about") for button in info_buttons)
    required_labels = [
        label.text()
        for label in window.window.findChildren(QtWidgets.QLabel)
        if "Required" in label.text() or "Hero card" in label.text()
    ]
    assert any("*" in label for label in required_labels)
    assert "* Required before analysis" in required_labels

    window.range_combo.setCurrentText("premium")
    window.advanced_mode_toggle.setChecked(True)
    assert window.advanced_opponents.isVisible()
    window.advanced_mode_toggle.setChecked(False)
    assert window.range_combo.currentText() == "premium"
    normal_state = window._state()
    assert normal_state.table_state is not None
    assert all(
        opponent.range_text == "random" and opponent.profile is OpponentProfile.UNKNOWN_BALANCED
        for opponent in normal_state.table_state.active_opponents
    )


def test_invalid_analysis_marks_and_focuses_first_required_card(
    window: MainWindow, qtbot: Any
) -> None:
    window.card_edits[0].clear()
    window.analyze()
    qtbot.waitUntil(window.card_edits[0].hasFocus, timeout=2_000)

    assert window.card_edits[0].property("validationError") is True
    assert "highlighted required fields" in window.output.toPlainText()
    assert window.thread is None


def test_results_have_overview_and_advanced_structure(window: MainWindow) -> None:
    assert [window.tabs.tabText(index) for index in range(window.tabs.count())] == [
        "Overview",
        "Advanced",
    ]
    assert [
        window.advanced_tabs.tabText(index) for index in range(window.advanced_tabs.count())
    ] == [
        "Detailed analysis",
        "Action comparison",
        "Probabilities",
        "Action table",
        "Copyable report",
    ]


def test_completed_analysis_populates_structured_overview(window: MainWindow, qtbot: Any) -> None:
    window.players.setValue(2)
    window.preset_combo.setCurrentText("Quick")
    window.analyze()
    qtbot.waitUntil(lambda: window.thread is None, timeout=15_000)

    assert window.overview_recommendation.text()
    assert "Showdown equity" in window.overview_key_numbers.text()
    assert "Best five" in window.overview_hand.text()
    assert "Entered Game State" in window.output.toPlainText()
    assert "Action-Aware Analysis" in window.output.toPlainText()
    assert window.action_table.columnCount() == 15
    action_text = window.advanced_section_bodies["Action-Aware Analysis"].text()
    assert "Second-best:" in action_text
    assert "EV gap" in action_text
    assert "branch EV" in action_text
    assert "weighted" in action_text
    titles = window.window.findChildren(QtWidgets.QLabel, "resultBlockTitle")
    bodies = window.window.findChildren(QtWidgets.QLabel, "resultBlockBody")
    assert len(titles) == 14
    assert all(title.text().endswith(":") for title in titles)
    assert all(title.font().bold() for title in titles)
    assert all(not body.font().bold() for body in bodies)
    assert set(window.advanced_section_bodies) == {
        "Entered Game State",
        "Current Hand",
        "Draw and Improvement Analysis",
        "Raw Showdown Analysis",
        "Opponent Assumptions",
        "Action-Aware Analysis",
        "Pot Odds and Expected Value",
        "Recommendation Reasoning",
    }
    assert window.latest_result is not None
    assert window.latest_result.action_aware is not None
    model_action = window.latest_result.action_aware.recommended_action
    assert model_action in window.overview_recommendation.text()
    assert model_action in window.advanced_section_bodies["Action-Aware Analysis"].text()
    comparison_cards = window.action_comparison_content.findChildren(
        QtWidgets.QFrame, "actionComparisonCard"
    )
    assert len(comparison_cards) == len(window.latest_result.action_aware.action_results)
    assert sum(bool(card.property("recommended")) for card in comparison_cards) == 1
    assert all(
        {bar.property("barKind") for bar in card.findChildren(QtWidgets.QProgressBar)}
        == {"negative", "positive"}
        for card in comparison_cards
    )
    candidate_labels = [
        item.candidate.label for item in window.latest_result.action_aware.action_results
    ]
    assert [
        window.action_table.item(row, 0).text() for row in range(window.action_table.rowCount())
    ] == candidate_labels
    assert all(
        label in window.advanced_section_bodies["Action-Aware Analysis"].text()
        for label in candidate_labels
    )
    assert all("Suggested size" not in body.text() for body in bodies)
    assert window.window.isVisible()


def test_non_all_in_85_chip_recommendation_matches_result_surfaces(window: MainWindow) -> None:
    game_state = GameState(
        active_players=2,
        hero_cards=cards("AS KS"),
        community_cards=cards("QS 10D 4S"),
        hero_position=Position.BUTTON,
        pot_size=100.0,
        amount_to_call=0.0,
        hero_stack=500.0,
        effective_stack=500.0,
        big_blind=10.0,
    )
    base = analyze_game_state(game_state, simulation_count=40, seed=9)
    forced_equity = replace(
        base.equity,
        win_percentage=0.80,
        loss_percentage=0.20,
        total_equity=0.80,
        pot_share_total=base.equity.iterations * 0.80,
    )
    result = replace(
        base,
        equity=forced_equity,
        recommendation=recommend_action(game_state, forced_equity, base.outs),
    )

    window._finished(result, window.analysis_id)
    assert result.recommendation.primary_action == "Bet 85 chips"
    assert window.overview_recommendation.text().startswith("Bet 85 chips")
    assert "Bet 85 chips" in window.advanced_section_bodies["Recommendation Reasoning"].text()
    assert "Bet 85 chips" in window.output.toPlainText()
    assert "all-in" not in window.overview_recommendation.text().casefold()
    assert "Suggested size" not in window.output.toPlainText()


def test_training_hides_answer_then_reveals_real_analysis(window: MainWindow, qtbot: Any) -> None:
    window._show_main_area()
    initial_seed = window.training_seed
    window.training()

    assert window.training_seed == initial_seed + 1
    assert window.training_state is not None
    first_state = window.training_state
    assert window.thread is None
    assert window.training_panel.isVisible()
    assert window.tabs.isHidden()
    assert "recommend" not in window.training_scenario.text().casefold()
    choices = window.training_choices.buttons()
    assert {button.text() for button in choices} == {
        candidate.label for candidate in generate_candidate_actions(first_state)
    }

    qtbot.mouseClick(choices[0], QtCore.Qt.MouseButton.LeftButton)
    qtbot.mouseClick(window.training_submit, QtCore.Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window.thread is None, timeout=15_000)
    assert window.latest_result is not None
    assert window.training_feedback.isVisible()
    assert "Recommended:" in window.training_feedback.text()
    assert window.training_badge.text() in {"Correct", "Incorrect"}
    assert window.training_attempted == 1
    assert window.window.isVisible()

    qtbot.mouseClick(window.training_next, QtCore.Qt.MouseButton.LeftButton)
    assert window.training_seed == initial_seed + 2
    assert window.training_state is not None
    assert window.training_state != first_state
    assert window.training_choice is None
    assert window.tabs.isHidden()
    second_choices = window.training_choices.buttons()
    qtbot.mouseClick(second_choices[-1], QtCore.Qt.MouseButton.LeftButton)
    assert second_choices[-1].isChecked()
    qtbot.mouseClick(window.training_submit, QtCore.Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window.thread is None, timeout=15_000)
    assert window.training_attempted == 2
    assert window.training_feedback.isVisible()
    assert window.training_next.isVisible()


def test_training_radio_choices_remain_visible_and_exclusive(
    window: MainWindow, qtbot: Any
) -> None:
    window._show_main_area()
    window.training()
    choices = window.training_choices.buttons()
    assert len(choices) >= 2

    for selected in choices:
        qtbot.mouseClick(selected, QtCore.Qt.MouseButton.LeftButton)
        assert selected.isChecked()
        assert selected.text()
        assert sum(button.isChecked() for button in choices) == 1
        assert window.training_submit.isEnabled()


def test_training_layout_stays_at_top_and_resets_for_repeated_hands(
    window: MainWindow, qtbot: Any
) -> None:
    window._show_main_area()
    window.window.resize(900, 620)
    window.training()
    qtbot.waitUntil(window.training_panel.isVisible, timeout=2_000)
    assert window.training_state is not None
    result = analyze_game_state(
        window.training_state,
        simulation_count=40,
        seed=7,
        include_action_aware=True,
        action_aware_settings=ActionAwareSettings(simulations_per_action=20),
    )
    initial_seed = window.training_seed
    section_titles = window.window.findChildren(QtWidgets.QLabel, "sectionTitle")
    results_title = next(label for label in section_titles if label.text() == "Results")
    table_title = next(label for label in section_titles if label.text() == "Table")
    assert window.training_panel.geometry().top() < window.tabs.geometry().top()
    assert (
        results_title.mapTo(window.window, QtCore.QPoint()).y()
        < window.training_panel.mapTo(window.window, QtCore.QPoint()).y()
    )
    assert (
        abs(
            results_title.mapTo(window.window, QtCore.QPoint()).y()
            - table_title.mapTo(window.window, QtCore.QPoint()).y()
        )
        <= 12
    )

    for cycle in range(5):
        choice = window.training_choices.buttons()[0]
        qtbot.mouseClick(choice, QtCore.Qt.MouseButton.LeftButton)
        assert choice.isChecked()
        window._reveal_training_result(result)
        assert window.training_attempted == cycle + 1
        assert window.training_feedback.isVisible()
        assert window.training_badge.text() in {"Correct", "Incorrect"}
        assert window.tabs.isHidden()
        if cycle == 0:
            qtbot.mouseClick(window.training_full, QtCore.Qt.MouseButton.LeftButton)
            qtbot.waitUntil(window.tabs.isVisible, timeout=2_000)
            assert window.training_scenario.isHidden()
            assert window.training_choice_scroll.isHidden()
            assert window.training_stats.isHidden()
            assert window.status_label.isHidden()
            assert window.progress.isHidden()
            assert window.training_feedback.isVisible()
            assert window.training_feedback.height() >= 96
            assert window.training_panel.geometry().bottom() <= window.tabs.geometry().top()
        qtbot.mouseClick(window.training_next, QtCore.Qt.MouseButton.LeftButton)
        assert window.training_seed == initial_seed + cycle + 1
        assert window.training_submit.isVisible()
        assert not window.training_submit.isEnabled()
        assert not window.training_feedback.isVisible()
        assert not window.training_badge.isVisible()
        assert window.training_scenario.isVisible()
        assert window.training_choice_scroll.isVisible()
        assert window.status_label.isVisible()
        assert window.progress.isVisible()
        assert not any(button.isChecked() for button in window.training_choices.buttons())


def test_training_correct_and_incorrect_badges_preserve_feedback(window: MainWindow) -> None:
    window._show_main_area()
    window.training()
    assert window.training_state is not None
    result = analyze_game_state(
        window.training_state,
        simulation_count=40,
        seed=11,
        include_action_aware=True,
        action_aware_settings=ActionAwareSettings(simulations_per_action=20),
    )
    assert result.action_aware is not None
    model = result.action_aware.recommended_action
    model_button = next(
        button for button in window.training_choices.buttons() if button.text() == model
    )

    model_button.setChecked(True)
    window._reveal_training_result(result)
    assert window.training_badge.text() == "Correct"
    assert model in window.training_feedback.text()
    assert window.training_feedback.isVisible()
    assert model_button.isChecked()

    window.training()
    different_button = next(
        button for button in window.training_choices.buttons() if button.text() != model
    )
    different_button.setChecked(True)
    different = different_button.text()
    window._reveal_training_result(result)
    assert window.training_badge.text() == "Incorrect"
    assert different in window.training_feedback.text()
    assert model in window.training_feedback.text()


def test_new_hand_then_training_restores_submit_choice(window: MainWindow) -> None:
    window._show_main_area()
    window.training()
    window.new_hand()
    assert not window.training_panel.isVisible()

    window.training()
    assert window.training_panel.isVisible()
    assert window.training_submit.isVisible()
    assert not window.training_submit.isEnabled()
    assert window.training_choice is None


def _open_terminology(
    window: MainWindow, qtbot: Any
) -> tuple[
    QtWidgets.QDialog,
    QtWidgets.QWidget,
    QtWidgets.QScrollArea,
    QtWidgets.QLineEdit,
    list[QtWidgets.QFrame],
]:
    window.about()
    assert window.help_dialog is not None
    qtbot.addWidget(window.help_dialog)
    qtbot.waitUntil(window.help_dialog.isVisible, timeout=2_000)
    dialog = window.help_dialog
    page = dialog.findChild(QtWidgets.QWidget, "terminologyPage")
    scroll = dialog.findChild(QtWidgets.QScrollArea, "terminologyScrollArea")
    search = dialog.findChild(QtWidgets.QLineEdit, "glossarySearch")
    assert page is not None
    assert scroll is not None
    assert search is not None
    tabs = dialog.findChild(QtWidgets.QTabWidget)
    assert tabs is not None
    tabs.setCurrentWidget(page)
    QtWidgets.QApplication.processEvents()
    cards = page.findChildren(QtWidgets.QFrame, "terminologyCard")
    return dialog, page, scroll, search, cards


def test_terminology_has_one_scrollable_card_layout(window: MainWindow, qtbot: Any) -> None:
    dialog, page, scroll, _search, cards = _open_terminology(window, qtbot)
    entries = main_window_module._terminology_entries()
    content = scroll.widget()

    assert len(dialog.findChildren(QtWidgets.QWidget, "terminologyPage")) == 1
    assert len(page.findChildren(QtWidgets.QScrollArea, "terminologyScrollArea")) == 1
    assert not page.findChildren(QtWidgets.QTreeWidget)
    assert content is not None
    assert content.objectName() == "terminologyContent"
    assert content.layout() is not None
    assert len(cards) == len(entries) == len(main_window_module._GLOSSARY)
    assert len({card.property("term") for card in cards}) == len(cards)
    assert all(term.strip() and definition.strip() for term, definition in entries)
    assert all(card.parentWidget() is content for card in cards)
    assert scroll.widgetResizable()
    dialog.resize(dialog.minimumSize())
    QtWidgets.QApplication.processEvents()
    assert scroll.verticalScrollBar().maximum() > 0


def test_terminology_cards_wrap_without_overlap_or_duplication(
    window: MainWindow, qtbot: Any
) -> None:
    dialog, _page, scroll, search, cards = _open_terminology(window, qtbot)
    expected_terms = {
        "Expected Value",
        "Conditional Equity",
        "Effective Stack",
        "Monte Carlo Simulation",
        "Action-Aware Model",
    }
    card_ids = tuple(id(card) for card in cards)
    term_labels = [card.findChild(QtWidgets.QLabel, "glossaryTerm") for card in cards]
    definition_labels = [card.findChild(QtWidgets.QLabel, "glossaryDefinition") for card in cards]
    assert all(label is not None for label in term_labels)
    assert all(label is not None for label in definition_labels)
    displayed_terms = {label.text() for label in term_labels if label is not None}
    assert expected_terms <= displayed_terms
    assert all("..." not in term and "…" not in term for term in displayed_terms)
    assert all(label.wordWrap() and label.font().bold() for label in term_labels if label)
    assert all(label.wordWrap() and not label.font().bold() for label in definition_labels if label)
    assert all(
        card.sizePolicy().verticalPolicy() == QtWidgets.QSizePolicy.Policy.Preferred
        and card.minimumHeight() != card.maximumHeight()
        for card in cards
    )

    dialog.resize(dialog.minimumSize())
    for theme in ("light", "dark"):
        window._apply_theme(theme)
        QtWidgets.QApplication.processEvents()
        assert tuple(id(card) for _term, _definition, card in window.terminology_cards) == card_ids
    for size in (QtCore.QSize(640, 440), QtCore.QSize(900, 620), QtCore.QSize(760, 560)):
        dialog.resize(size)
        QtWidgets.QApplication.processEvents()
        assert tuple(id(card) for _term, _definition, card in window.terminology_cards) == card_ids
    for query in ("equity", "GTO", "simulation", "", "stack", ""):
        search.setText(query)
        QtWidgets.QApplication.processEvents()
        assert tuple(id(card) for _term, _definition, card in window.terminology_cards) == card_ids
        assert len(dialog.findChildren(QtWidgets.QFrame, "terminologyCard")) == len(cards)

    content = scroll.widget()
    assert content is not None
    assert content.layout() is not None
    content.layout().activate()
    visible_cards = [card for card in cards if not card.isHidden()]
    assert all(card.height() >= card.minimumSizeHint().height() for card in visible_cards)
    assert all(
        not first.geometry().intersects(second.geometry())
        for first, second in zip(visible_cards, visible_cards[1:], strict=False)
    )
    assert all(
        label is not None and label.text().strip() and not label.isHidden() and label.height() > 0
        for label in definition_labels
    )


def test_reopening_terminology_keeps_one_card_set_and_one_search_connection(
    window: MainWindow, qtbot: Any
) -> None:
    expected_count = len(main_window_module._GLOSSARY)
    for _ in range(4):
        dialog, page, _scroll, search, cards = _open_terminology(window, qtbot)
        assert len(cards) == expected_count
        assert len(page.findChildren(QtWidgets.QFrame, "terminologyCard")) == expected_count
        assert search.receivers(QtCore.SIGNAL("textChanged(QString)")) == 1
        search.setText("Expected Value")
        QtWidgets.QApplication.processEvents()
        assert [card.property("term") for card in cards if not card.isHidden()] == [
            "Expected Value"
        ]
        dialog.close()
        qtbot.waitUntil(lambda: window.help_dialog is None, timeout=2_000)
        assert not window.terminology_cards


def test_new_hand_resets_cards_players_betting_and_opponents(window: MainWindow) -> None:
    window.advanced_mode_toggle.setChecked(True)
    window.players.setValue(3)
    window.pot.setValue(999.0)
    window.folded_seats.setText("2")
    window.range_combo.setCurrentText("premium")
    window.player_overrides[1] = window._build_table_state("flop").player(1)

    window.new_hand()

    assert all(not edit.text() for edit in window.card_edits)
    assert window.players.value() == window.settings.default_player_count
    assert window.pot.value() == 140.0
    assert not window.folded_seats.text()
    assert window.range_combo.currentText() == "random"
    assert not window.player_overrides
    assert window.latest_result is None


def test_settings_dialog_omits_redundant_advanced_control(
    window: MainWindow,
    qtbot: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[QtWidgets.QDialog] = []

    def reject_dialog(dialog: QtWidgets.QDialog) -> QtWidgets.QDialog.DialogCode:
        captured.append(dialog)
        return QtWidgets.QDialog.DialogCode.Rejected

    monkeypatch.setattr(QtWidgets.QDialog, "exec", reject_dialog)
    window.settings_dialog()
    assert len(captured) == 1
    dialog = captured[0]
    qtbot.addWidget(dialog)
    checkbox_text = {checkbox.text() for checkbox in dialog.findChildren(QtWidgets.QCheckBox)}
    assert "Show advanced settings" not in checkbox_text

    window._show_main_area()
    window.advanced_mode_toggle.setChecked(True)
    assert window.settings.advanced_mode is True
    assert window.advanced_opponents.isVisible()


def test_card_picker_has_spacing_scrolls_and_none_clears(
    window: MainWindow,
    qtbot: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[QtWidgets.QDialog] = []

    def capture_dialog(dialog: QtWidgets.QDialog) -> QtWidgets.QDialog.DialogCode:
        captured.append(dialog)
        return QtWidgets.QDialog.DialogCode.Rejected

    monkeypatch.setattr(QtWidgets.QDialog, "exec", capture_dialog)
    window._show_main_area()
    window.window.resize(900, 620)
    field = window.card_edits[0]
    pick_buttons = window.window.findChildren(QtWidgets.QPushButton, "pickCardButton")
    field_right = field.mapTo(window.window, QtCore.QPoint(field.width(), 0)).x()
    button_left = pick_buttons[0].mapTo(window.window, QtCore.QPoint()).x()
    assert button_left - field_right >= 8

    window._pick_card(field)
    dialog = captured[0]
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitUntil(dialog.isVisible, timeout=2_000)
    scroll = dialog.findChild(QtWidgets.QScrollArea, "cardPickerScroll")
    clear_button = dialog.findChild(QtWidgets.QPushButton, "cardPickerNone")
    assert scroll is not None
    assert clear_button is not None
    assert scroll.verticalScrollBar().maximum() > 0
    screen = dialog.screen() or QtWidgets.QApplication.primaryScreen()
    assert screen is not None
    available = screen.availableGeometry()
    assert dialog.width() <= available.width() - 40
    assert dialog.height() <= available.height() - 80

    qtbot.mouseClick(clear_button, QtCore.Qt.MouseButton.LeftButton)
    assert not field.text()


def test_opponent_editor_rows_do_not_clip_controls(
    window: MainWindow,
    qtbot: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[QtWidgets.QDialog] = []

    def capture_dialog(dialog: QtWidgets.QDialog) -> QtWidgets.QDialog.DialogCode:
        captured.append(dialog)
        return QtWidgets.QDialog.DialogCode.Rejected

    monkeypatch.setattr(QtWidgets.QDialog, "exec", capture_dialog)
    window.advanced_mode_toggle.setChecked(True)
    window.opponent_editor()
    dialog = captured[0]
    qtbot.addWidget(dialog)
    editor = dialog.findChild(QtWidgets.QTableWidget)
    assert editor is not None
    assert all(editor.rowHeight(row) >= 44 for row in range(editor.rowCount()))
    for row in range(editor.rowCount()):
        for column in (1, 4, 5, 6, 7):
            control = editor.cellWidget(row, column)
            assert control is not None
            assert control.minimumHeight() >= 34


def test_combo_arrow_tracks_mouse_and_keyboard_popup_paths(window: MainWindow, qtbot: Any) -> None:
    window._show_main_area()
    combo = window.position
    assert combo.property("popupOpen") is False

    combo.showPopup()
    qtbot.waitUntil(lambda: combo.property("popupOpen") is True, timeout=2_000)
    qtbot.keyClick(combo.view(), QtCore.Qt.Key.Key_Escape)
    qtbot.waitUntil(lambda: combo.property("popupOpen") is False, timeout=2_000)

    combo.setFocus()
    qtbot.keyClick(
        combo,
        QtCore.Qt.Key.Key_Down,
        modifier=QtCore.Qt.KeyboardModifier.AltModifier,
    )
    qtbot.waitUntil(lambda: combo.property("popupOpen") is True, timeout=2_000)
    combo.hidePopup()
    assert combo.property("popupOpen") is False
    combo.setEnabled(False)
    assert not combo.grab().isNull()


def test_validation_marks_all_invalid_fields_and_clears_each_correction(
    window: MainWindow, qtbot: Any
) -> None:
    window._show_main_area()
    window.card_edits[0].clear()
    window.card_edits[1].clear()
    window.card_edits[3].clear()
    window.card_edits[4].clear()
    window.call.setValue(950.0)
    window.analyze()
    qtbot.waitUntil(window.card_edits[0].hasFocus, timeout=2_000)

    for index in (0, 1, 3, 4):
        assert window.card_edits[index].property("validationError") is True
        assert window.card_edits[index].accessibleDescription()
    for index in (2, 5, 6):
        assert window.card_edits[index].property("validationError") is not True
    assert window.call.property("validationError") is True
    assert window.stack.property("validationError") is True

    window.card_edits[0].setText("AS")
    window.card_edits[3].setText("10D")
    window.call.setValue(40.0)
    assert window.card_edits[0].property("validationError") is False
    assert window.card_edits[3].property("validationError") is False
    assert window.call.property("validationError") is False
    assert window.stack.property("validationError") is False
    assert window.card_edits[1].property("validationError") is True
    assert window.card_edits[4].property("validationError") is True


def test_duplicate_cards_mark_both_fields_until_corrected(window: MainWindow) -> None:
    window.card_edits[1].setText("AS")
    window.analyze()
    assert window.card_edits[0].property("validationError") is True
    assert window.card_edits[1].property("validationError") is True
    assert "duplicated" in window.card_edits[0].toolTip()

    window.card_edits[1].setText("KS")
    assert window.card_edits[0].property("validationError") is False
    assert window.card_edits[1].property("validationError") is False


def test_stack_step_buttons_use_full_click_targets_and_bound_states(
    window: MainWindow, qtbot: Any
) -> None:
    container, spin = window._stack_control(5.0)
    qtbot.addWidget(container)
    container.show()
    buttons = container.findChildren(QtWidgets.QToolButton)
    decrease = next(button for button in buttons if button.text() == "-")
    increase = next(button for button in buttons if button.text() == "+")

    qtbot.mouseClick(increase, QtCore.Qt.MouseButton.LeftButton)
    assert spin.value() == 6.0
    qtbot.mouseClick(decrease, QtCore.Qt.MouseButton.LeftButton)
    assert spin.value() == 5.0

    spin.setValue(spin.minimum())
    assert not decrease.isEnabled()
    assert increase.isEnabled()
    spin.setValue(spin.maximum())
    assert decrease.isEnabled()
    assert not increase.isEnabled()


def test_landing_navigation_and_theme_toggle(window: MainWindow, qtbot: Any) -> None:
    enter = window.window.findChild(QtWidgets.QPushButton, "landingEnter")
    assert enter is not None
    assert window._landing_page.isVisible()
    assert window._main_area.isHidden()

    qtbot.mouseClick(enter, QtCore.Qt.MouseButton.LeftButton)
    assert window._main_area.isVisible()
    assert window._landing_page.isHidden()
    qtbot.mouseClick(window.theme_toggle, QtCore.Qt.MouseButton.LeftButton)
    assert window.settings.theme == "dark"
    assert "#1C2128" in window.window.styleSheet()
    qtbot.mouseClick(window.home_button, QtCore.Qt.MouseButton.LeftButton)
    assert window._landing_page.isVisible()


def test_save_load_and_export_buttons_remain_connected(
    window: MainWindow,
    qtbot: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    hand_path = tmp_path / "ui-hand.json"
    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getSaveFileName",
        lambda *_args: (str(hand_path), "JSON Files (*.json)"),
    )
    qtbot.mouseClick(window.save_button, QtCore.Qt.MouseButton.LeftButton)
    assert hand_path.exists()

    window.card_edits[0].setText("AH")
    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getOpenFileName",
        lambda *_args: (str(hand_path), "JSON Files (*.json)"),
    )
    qtbot.mouseClick(window.load_button, QtCore.Qt.MouseButton.LeftButton)
    assert window.card_edits[0].text() == "AS"

    window.latest_result = analyze_game_state(window._state(), simulation_count=100, seed=3)
    window._sync_button_states()
    export_path = tmp_path / "ui-analysis.md"
    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getSaveFileName",
        lambda *_args: (str(export_path), "Markdown (*.md)"),
    )
    qtbot.mouseClick(window.export_button, QtCore.Qt.MouseButton.LeftButton)
    assert "Peaceful Poker Analysis" in export_path.read_text(encoding="utf-8")
