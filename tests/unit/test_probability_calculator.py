"""Tests for exact final-hand probability calculations."""

from math import isclose

from poker_trainer.engine.hand_evaluator import evaluate_best_hand
from poker_trainer.engine.probability_calculator import calculate_final_hand_probabilities
from poker_trainer.models import Card, GameState, HandCategory, Position


def cards(codes: str) -> tuple[Card, ...]:
    """Create cards from a whitespace-separated code list."""
    return tuple(Card.from_code(code) for code in codes.split())


def state(hero: str, board: str) -> GameState:
    """Create a test game state."""
    return GameState(
        active_players=2,
        hero_cards=cards(hero),
        community_cards=cards(board),
        hero_position=Position.BUTTON,
    )


def test_preflop_exact_calculation_is_deferred() -> None:
    result = calculate_final_hand_probabilities(state("AS KS", ""))

    assert result.runouts_examined == 0
    assert result.current_category is None
    assert result.warnings


def test_turn_calculation_has_correct_number_of_river_runouts() -> None:
    result = calculate_final_hand_probabilities(state("AS KS", "QS 7S 2C 3D"))

    assert result.runouts_examined == 46


def test_flop_calculation_has_correct_number_of_unordered_two_card_runouts() -> None:
    result = calculate_final_hand_probabilities(state("AS KS", "QS 7S 2C"))

    assert result.runouts_examined == 1081


def test_river_category_probability_equals_one() -> None:
    result = calculate_final_hand_probabilities(state("AS KS", "QS JS 10S 2D 3C"))

    assert result.runouts_examined == 1
    assert result.exact_category_probabilities[HandCategory.STRAIGHT_FLUSH] == 1.0


def test_exact_category_probabilities_sum_to_one() -> None:
    result = calculate_final_hand_probabilities(state("AS KS", "QS 7S 2C 3D"))

    assert isclose(sum(result.exact_category_probabilities.values()), 1.0)


def test_at_least_probabilities_are_monotonic() -> None:
    result = calculate_final_hand_probabilities(state("AS KS", "QS 7S 2C 3D"))
    ordered = [result.at_least_category_probabilities[category] for category in HandCategory]

    assert ordered == sorted(ordered, reverse=True)


def test_flush_completion_probability_on_turn() -> None:
    result = calculate_final_hand_probabilities(state("AS KS", "QS 7S 2C 3D"))

    assert isclose(result.exact_category_probabilities[HandCategory.FLUSH], 9 / 46)


def test_ace_low_straight_completion_probability_on_turn() -> None:
    result = calculate_final_hand_probabilities(state("AS KD", "2C 3H 4S 9D"))

    assert isclose(result.exact_category_probabilities[HandCategory.STRAIGHT], 4 / 46)


def test_full_house_redraw_improvement_probability() -> None:
    result = calculate_final_hand_probabilities(state("AS AH", "AD 7C 7D 2S"))

    assert isclose(result.exact_category_probabilities[HandCategory.FOUR_OF_A_KIND], 1 / 46)
    assert isclose(result.improvement_probability, 1 / 46)


def test_current_evaluator_is_used_consistently_on_river() -> None:
    game_state = state("AS AH", "AD 7C 7D 2S AC")
    result = calculate_final_hand_probabilities(game_state)
    evaluated = evaluate_best_hand(game_state.known_cards)

    assert result.current_category is evaluated.category
    assert result.exact_category_probabilities[evaluated.category] == 1.0
