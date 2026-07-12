"""Integrated acceptance scenario for the Peaceful Poker analyzer."""

from pathlib import Path

from poker_trainer.engine.draw_detector import DrawType
from poker_trainer.models import Card, GameState, Position
from poker_trainer.services.analysis_service import analyze_game_state
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
