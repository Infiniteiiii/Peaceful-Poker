"""Regression tests for canonical, context-aware action labels."""

from poker_trainer.engine.candidate_actions import generate_candidate_actions
from poker_trainer.models import Card, GameState, HeroActionKind, Position, create_default_table
from poker_trainer.strategy.action_labels import format_action, format_legal_action
from poker_trainer.strategy.legal_actions import PlayerAction, legal_actions


def cards(codes: str) -> tuple[Card, ...]:
    return tuple(Card.from_code(code) for code in codes.split())


def state(*, call: float = 0.0, stack: float = 500.0, pot: float = 100.0) -> GameState:
    table = create_default_table(2, Position.BUTTON.value, "flop", stack, stack)
    return GameState(
        active_players=2,
        hero_cards=cards("AS KS"),
        community_cards=cards("QS 10D 4S"),
        hero_position=Position.BUTTON,
        pot_size=pot,
        amount_to_call=call,
        hero_stack=stack,
        effective_stack=stack,
        big_blind=10.0,
        table_state=table,
    )


def test_passive_action_labels_are_context_aware() -> None:
    facing = state(call=20.0)

    assert format_action(PlayerAction.CHECK, state()) == "Check"
    assert format_action(PlayerAction.FOLD, facing) == "Fold"
    assert format_legal_action(PlayerAction.CALL, facing) == "Call 20 chips"


def test_bet_raise_and_all_in_labels_use_exact_chip_conventions() -> None:
    checked = state(stack=100.0)
    facing = state(call=20.0, stack=100.0)

    assert format_action(HeroActionKind.BET, checked, additional_investment=85.0) == "Bet 85 chips"
    assert (
        format_action(
            HeroActionKind.RAISE,
            facing,
            additional_investment=40.0,
            target_round_contribution=60.0,
        )
        == "Raise to 60 chips"
    )
    assert format_legal_action(PlayerAction.ALL_IN, checked) == "Bet all-in \u2014 100 chips"
    assert (
        format_action(HeroActionKind.BET, checked, additional_investment=100.0)
        == "Bet all-in \u2014 100 chips"
    )
    assert (
        format_action(
            HeroActionKind.ALL_IN,
            facing,
            additional_investment=100.0,
            target_round_contribution=100.0,
        )
        == "Raise all-in to 100 chips"
    )
    assert (
        format_legal_action(PlayerAction.ALL_IN, state(call=100.0, stack=100.0))
        == "Call all-in \u2014 100 chips"
    )


def test_legal_actions_do_not_duplicate_stack_committing_choices() -> None:
    assert legal_actions(state(stack=10.0)) == (PlayerAction.CHECK, PlayerAction.ALL_IN)
    assert legal_actions(state(call=100.0, stack=100.0)) == (
        PlayerAction.FOLD,
        PlayerAction.ALL_IN,
    )


def test_candidate_labels_are_unique_and_match_their_structured_action() -> None:
    game_state = state(call=20.0, stack=100.0)
    candidates = generate_candidate_actions(game_state)

    assert len({candidate.label for candidate in candidates}) == len(candidates)
    assert {candidate.label for candidate in candidates} >= {
        "Fold",
        "Call 20 chips",
        "Raise to 40 chips",
        "Raise all-in to 100 chips",
    }
