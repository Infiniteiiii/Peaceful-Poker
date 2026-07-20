"""Tests for pot odds, legal actions, and recommendations."""

from poker_trainer.models import Card, EquityResult, GameState, Position
from poker_trainer.strategy.action_recommender import recommend_action
from poker_trainer.strategy.legal_actions import PlayerAction, legal_actions
from poker_trainer.strategy.pot_odds import calculate_pot_odds


def cards(codes: str) -> tuple[Card, ...]:
    return tuple(Card.from_code(code) for code in codes.split())


def state(call: float, stack: float = 100.0, pot: float = 150.0) -> GameState:
    return GameState(
        active_players=2,
        hero_cards=cards("AS KS"),
        community_cards=cards("QS 10D 4S"),
        hero_position=Position.BUTTON,
        pot_size=pot,
        amount_to_call=call,
        hero_stack=stack,
    )


def equity(value: float) -> EquityResult:
    return EquityResult(
        wins=0,
        losses=0,
        ties=0,
        pot_share_total=value,
        win_percentage=value,
        loss_percentage=1 - value,
        tie_percentage=0.0,
        total_equity=value,
        iterations=1,
        calculation_method="test",
        random_seed=None,
        execution_time=0.0,
        warnings=(),
        assumptions=("test",),
    )


def test_required_equity_uses_documented_pot_definition() -> None:
    result = calculate_pot_odds(150.0, 50.0, 0.30)

    assert result.final_pot_after_call == 200.0
    assert result.required_equity == 0.25
    assert result.simplified_call_ev == 0.30 * 150.0 - 0.70 * 50.0


def test_zero_call_legal_actions_are_check_bet_all_in() -> None:
    actions = legal_actions(state(0.0))

    assert PlayerAction.CHECK in actions
    assert PlayerAction.CALL not in actions


def test_facing_bet_legal_actions() -> None:
    actions = legal_actions(state(40.0, stack=100.0))

    assert PlayerAction.FOLD in actions
    assert PlayerAction.CALL in actions
    assert PlayerAction.RAISE in actions


def test_all_in_call_edge() -> None:
    actions = legal_actions(state(100.0, stack=100.0))

    assert PlayerAction.ALL_IN in actions
    assert PlayerAction.RAISE not in actions


def test_profitable_all_in_call_is_recommended_as_all_in() -> None:
    recommendation = recommend_action(state(100.0, stack=100.0, pot=400.0), equity(0.60))

    assert recommendation.primary_action == "Call all-in \u2014 100 chips"
    assert recommendation.primary_action in recommendation.legal_alternatives


def test_recommend_fold_when_below_required_equity() -> None:
    recommendation = recommend_action(state(50.0), equity(0.10))

    assert recommendation.primary_action == "Fold"


def test_recommend_call_when_above_required_equity() -> None:
    recommendation = recommend_action(state(50.0), equity(0.40))

    assert recommendation.primary_action == "Call 50 chips"
    assert "guaranteed" not in recommendation.explanation.lower()


def test_recommend_value_bet_when_checked_to() -> None:
    recommendation = recommend_action(state(0.0), equity(0.70))

    assert recommendation.primary_action == "Bet 90 chips"
    assert recommendation.suggested_size == 90.0


def test_recommendation_keeps_an_85_chip_bet_distinct_from_all_in() -> None:
    recommendation = recommend_action(state(0.0, stack=500.0, pot=100.0), equity(0.80))

    assert recommendation.primary_action == "Bet 85 chips"
    assert recommendation.suggested_size == 85.0
    assert "all-in" not in recommendation.primary_action.casefold()


def test_stack_committing_85_chip_bet_is_labelled_all_in() -> None:
    recommendation = recommend_action(state(0.0, stack=85.0, pot=100.0), equity(0.80))

    assert recommendation.primary_action == "Bet all-in \u2014 85 chips"
    assert recommendation.suggested_size == 85.0


def test_missing_equity_returns_legal_passive_guidance() -> None:
    recommendation = recommend_action(state(0.0), None)

    assert recommendation.primary_action == "Check"
    assert recommendation.confidence.value == "low"
