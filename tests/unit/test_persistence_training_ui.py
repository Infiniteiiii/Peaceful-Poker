"""Tests for persistence, export, settings, training, and UI startup."""

from pathlib import Path

import pytest

from poker_trainer.app import run
from poker_trainer.models import Card, GameState, Position
from poker_trainer.services.analysis_service import analyze_game_state
from poker_trainer.services.export_service import export_analysis_json, export_analysis_markdown
from poker_trainer.services.settings_service import UserSettings, load_settings, save_settings
from poker_trainer.services.storage_service import SavedHand, load_hand, save_hand
from poker_trainer.training.training_service import TrainingDifficulty, generate_scenario
from poker_trainer.utils.exceptions import (
    DuplicateCardError,
    StorageError,
    UnsupportedSaveVersionError,
)


def cards(codes: str) -> tuple[Card, ...]:
    return tuple(Card.from_code(code) for code in codes.split())


def state() -> GameState:
    return GameState(
        active_players=6,
        hero_cards=cards("AS KS"),
        community_cards=cards("QS 10D 4S"),
        hero_position=Position.BUTTON,
        pot_size=140.0,
        amount_to_call=40.0,
        hero_stack=900.0,
        effective_stack=620.0,
        small_blind=5.0,
        big_blind=10.0,
        requested_simulation_count=200,
    )


def test_save_load_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "hand.json"
    save_hand(SavedHand(state(), "tight", "note"), path)
    loaded = load_hand(path)

    assert loaded.game_state.hero_cards == state().hero_cards
    assert loaded.opponent_range == "tight"
    assert loaded.notes == "note"


def test_invalid_json_and_future_version(tmp_path: Path) -> None:
    invalid = tmp_path / "bad.json"
    invalid.write_text("not-json", encoding="utf-8")
    with pytest.raises(StorageError):
        load_hand(invalid)
    future = tmp_path / "future.json"
    future.write_text('{"schema_version": 999}', encoding="utf-8")
    with pytest.raises(UnsupportedSaveVersionError):
        load_hand(future)


def test_duplicate_cards_in_loaded_data_raise(tmp_path: Path) -> None:
    path = tmp_path / "dup.json"
    path.write_text(
        """
        {
          "schema_version": 1,
          "active_players": 2,
          "hero_cards": ["AS", "KS"],
          "community_cards": ["AS", "10D", "4S"],
          "hero_position": "button",
          "pot_size": 0,
          "amount_to_call": 0,
          "hero_stack": 0,
          "effective_stack": 0,
          "small_blind": 0,
          "big_blind": 0,
          "ante": 0,
          "requested_simulation_count": 100
        }
        """,
        encoding="utf-8",
    )

    with pytest.raises(DuplicateCardError):
        load_hand(path)


def test_settings_persistence(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    save_settings(UserSettings(theme="dark", default_player_count=9), path)

    assert load_settings(path).theme == "dark"
    assert load_settings(path).default_player_count == 9


def test_export_contents(tmp_path: Path) -> None:
    result = analyze_game_state(state(), simulation_count=100, seed=1)
    markdown = export_analysis_markdown(result, tmp_path / "analysis.md")
    json_path = export_analysis_json(result, tmp_path / "analysis.json")

    assert "Peaceful Poker Analysis" in markdown.read_text(encoding="utf-8")
    assert "recommendation" in json_path.read_text(encoding="utf-8")


def test_training_scenario_uses_real_analysis() -> None:
    scenario = generate_scenario(TrainingDifficulty.BEGINNER, seed=1)

    assert scenario.analysis.recommendation.primary_action in scenario.legal_action_labels
    assert scenario.game_state.active_players >= 2


def test_application_startup_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("PEACEFUL_POKER_AUTOCLOSE_MS", "10")

    assert run() == 0
