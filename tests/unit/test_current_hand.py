"""Tests for current-hand analysis."""

from poker_trainer.engine.current_hand import analyze_current_hand
from poker_trainer.models import Card, GameState, HandCategory, Position


def cards(codes: str) -> tuple[Card, ...]:
    """Create cards from a whitespace-separated code list."""
    return tuple(Card.from_code(code) for code in codes.split())


def state(hero: str, board: str = "") -> GameState:
    """Create a test game state."""
    return GameState(
        active_players=2,
        hero_cards=cards(hero),
        community_cards=cards(board),
        hero_position=Position.BUTTON,
    )


def test_preflop_pair_description() -> None:
    analysis = analyze_current_hand(state("AS AH"))

    assert analysis.is_preflop
    assert analysis.description == "Pair of Aces"
    assert analysis.evaluated_hand is None


def test_preflop_suited_description() -> None:
    assert analyze_current_hand(state("AS KS")).description == "Ace-King suited"


def test_preflop_offsuit_description() -> None:
    assert analyze_current_hand(state("QH JC")).description == "Queen-Jack offsuit"


def test_flop_made_hand() -> None:
    analysis = analyze_current_hand(state("AS AH", "7D 2C 9S"))

    assert analysis.evaluated_hand is not None
    assert analysis.evaluated_hand.category is HandCategory.PAIR


def test_turn_made_hand() -> None:
    analysis = analyze_current_hand(state("AS KS", "QS JS 10C 2D"))

    assert analysis.evaluated_hand is not None
    assert analysis.evaluated_hand.category is HandCategory.STRAIGHT
    assert analysis.hero_cards_used == 2


def test_river_made_hand() -> None:
    analysis = analyze_current_hand(state("AS KS", "QS JS 10S 2D 3C"))

    assert analysis.evaluated_hand is not None
    assert analysis.evaluated_hand.display_category == "Royal Flush"


def test_board_only_best_hand_uses_zero_hero_cards() -> None:
    analysis = analyze_current_hand(state("AS KD", "2H 3D 4C 5S 6H"))

    assert analysis.hero_cards_used == 0
    assert analysis.evaluated_hand is not None
    assert analysis.evaluated_hand.category is HandCategory.STRAIGHT


def test_hero_using_one_private_card() -> None:
    analysis = analyze_current_hand(state("AS 7D", "KS QS JS 10C 2H"))

    assert analysis.hero_cards_used == 1


def test_hero_using_two_private_cards() -> None:
    analysis = analyze_current_hand(state("AS KS", "QS JS 10C 2D 3H"))

    assert analysis.hero_cards_used == 2
