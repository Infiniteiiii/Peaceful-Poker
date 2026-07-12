"""Integrated acceptance scenario for the Peaceful Poker analyzer."""

from dataclasses import replace
from pathlib import Path

from poker_trainer.engine.draw_detector import DrawType
from poker_trainer.models import Card, GameState, Position
from poker_trainer.services.analysis_service import analyze_game_state
from poker_trainer.services.export_service import export_analysis_json, export_analysis_markdown
from poker_trainer.services.storage_service import SavedHand, load_hand, save_hand


def cards(codes: str) -> tuple[Card, ...]:
    return tuple(Card.from_code(code) for code in codes.split())


def test_specified_analyzer_scenario_round_trip(tmp_path: Path) -> None:
    game_state = GameState(
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
        requested_simulation_count=500,
    )

    result = analyze_game_state(game_state, simulation_count=500, seed=7)
    draw_types = {draw.draw_type for draw in result.draws}

    assert "High card, Ace" in result.current_hand.description
    assert DrawType.FLUSH_DRAW in draw_types
    assert DrawType.GUTSHOT_STRAIGHT_DRAW in draw_types
    assert DrawType.TWO_OVERCARDS in draw_types
    assert result.pot_odds.required_equity == 40 / 180
    assert result.recommendation.primary_action in result.recommendation.legal_alternatives
    assert 0.0 <= result.equity.total_equity <= 1.0

    path = save_hand(SavedHand(game_state, "random", "acceptance"), tmp_path / "hand.json")
    loaded = load_hand(path)

    assert loaded.game_state.hero_cards == game_state.hero_cards
    assert loaded.game_state.community_cards == game_state.community_cards

    turn_state = replace(game_state, community_cards=cards("QS 10D 4S 2C"))
    turn_result = analyze_game_state(turn_state, simulation_count=200, seed=7)
    river_state = replace(game_state, community_cards=cards("QS 10D 4S 2C 3S"))
    river_result = analyze_game_state(river_state, simulation_count=200, seed=7)
    markdown = export_analysis_markdown(river_result, tmp_path / "analysis.md")
    json_report = export_analysis_json(river_result, tmp_path / "analysis.json")

    assert turn_result.current_hand.evaluated_hand is not None
    assert river_result.current_hand.evaluated_hand is not None
    assert markdown.exists()
    assert json_report.exists()
