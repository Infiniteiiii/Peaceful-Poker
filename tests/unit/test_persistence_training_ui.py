"""Tests for persistence, export, settings, training, and UI startup."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from poker_trainer.app import run
from poker_trainer.models import Card, GameState, OpponentProfile, Position
from poker_trainer.services.analysis_service import analyze_game_state
from poker_trainer.services.export_service import export_analysis_json, export_analysis_markdown
from poker_trainer.services.settings_service import UserSettings, load_settings, save_settings
from poker_trainer.services.storage_service import SavedHand, load_hand, save_hand
from poker_trainer.training.training_service import (
    TrainingDifficulty,
    TrainingSituation,
    generate_scenario,
    generate_training_state,
)
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
    assert loaded.source_schema_version == 2
    assert loaded.game_state.table_state is not None


def test_version_one_save_migrates_to_default_balanced_opponents(tmp_path: Path) -> None:
    path = tmp_path / "legacy.json"
    save_hand(SavedHand(state(), "tight", "legacy"), path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["schema_version"] = 1
    payload.pop("table_state")
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_hand(path)

    assert loaded.source_schema_version == 1
    assert loaded.game_state.table_state is not None
    assert all(
        player.profile is OpponentProfile.UNKNOWN_BALANCED
        for player in loaded.game_state.table_state.active_opponents
    )


def test_version_two_opponent_states_round_trip(tmp_path: Path) -> None:
    game_state = state()
    assert game_state.table_state is not None
    players = tuple(
        replace(player, profile=OpponentProfile.LOOSE_AGGRESSIVE, range_text="loose")
        if not player.is_hero
        else player
        for player in game_state.table_state.players
    )
    configured = replace(game_state, table_state=replace(game_state.table_state, players=players))
    path = save_hand(SavedHand(configured), tmp_path / "configured.json")

    loaded = load_hand(path)

    assert loaded.game_state.table_state is not None
    assert all(
        player.profile is OpponentProfile.LOOSE_AGGRESSIVE
        for player in loaded.game_state.table_state.active_opponents
    )


def test_invalid_version_two_action_state_is_rejected(tmp_path: Path) -> None:
    path = save_hand(SavedHand(state()), tmp_path / "invalid-table.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    opponent = next(player for player in payload["table_state"]["players"] if not player["is_hero"])
    opponent["folded"] = True
    opponent["all_in"] = True
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(StorageError):
        load_hand(path)


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


def test_invalid_settings_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text('{"theme": "invisible"}', encoding="utf-8")

    with pytest.raises(StorageError):
        load_settings(path)


def test_export_contents(tmp_path: Path) -> None:
    result = analyze_game_state(state(), simulation_count=100, seed=1)
    markdown = export_analysis_markdown(result, tmp_path / "analysis.md")
    json_path = export_analysis_json(result, tmp_path / "analysis.json")

    assert "Peaceful Poker Analysis" in markdown.read_text(encoding="utf-8")
    assert "recommendation" in json_path.read_text(encoding="utf-8")


def test_training_scenario_uses_real_analysis() -> None:
    scenario = generate_scenario(TrainingDifficulty.BEGINNER, seed=1)

    assert scenario.analysis.recommendation.primary_action in scenario.legal_action_labels
    assert scenario.analysis.action_aware is not None
    assert scenario.game_state.active_players >= 2
    assert "remain to act behind hero" in scenario.action_order_explanation


@pytest.mark.parametrize(
    ("situation", "expected_behind"),
    [
        (TrainingSituation.LAST_TO_ACT, 0),
        (TrainingSituation.ONE_BEHIND, 1),
        (TrainingSituation.SEVERAL_BEHIND, 3),
        (TrainingSituation.TIGHT_BEHIND, 3),
        (TrainingSituation.LOOSE_AGGRESSIVE_BEHIND, 3),
        (TrainingSituation.SHORT_STACK_BEHIND, 2),
        (TrainingSituation.PRIOR_CALLERS, 0),
    ],
)
def test_training_action_order_situations(
    situation: TrainingSituation, expected_behind: int
) -> None:
    game_state = generate_training_state(
        TrainingDifficulty.ADVANCED,
        seed=4,
        situation=situation,
    )

    assert game_state.table_state is not None
    assert len(game_state.table_state.players_after_hero()) == expected_behind
    if situation is TrainingSituation.TIGHT_BEHIND:
        assert all(
            player.profile is OpponentProfile.TIGHT_PASSIVE
            for player in game_state.table_state.players_after_hero()
        )
    if situation is TrainingSituation.LOOSE_AGGRESSIVE_BEHIND:
        assert all(
            player.profile is OpponentProfile.LOOSE_AGGRESSIVE
            for player in game_state.table_state.players_after_hero()
        )
    if situation is TrainingSituation.SHORT_STACK_BEHIND:
        assert all(player.stack <= 60 for player in game_state.table_state.players_after_hero())
    if situation is TrainingSituation.PRIOR_CALLERS:
        assert any(
            "Called" in player.previous_actions
            for player in game_state.table_state.active_opponents
        )


def test_smoke_behavior_requires_explicit_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    from poker_trainer.app import smoke_test_enabled

    monkeypatch.setenv("PEACEFUL_POKER_SMOKE_REPORT", "ignored.json")
    monkeypatch.setenv("PEACEFUL_POKER_AUTOCLOSE_MS", "10")
    monkeypatch.delenv("PEACEFUL_POKER_SMOKE_TEST", raising=False)

    assert not smoke_test_enabled()


def test_application_startup_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("PEACEFUL_POKER_SMOKE_TEST", "1")
    monkeypatch.setenv("PEACEFUL_POKER_AUTOCLOSE_MS", "10")

    assert run() == 0
