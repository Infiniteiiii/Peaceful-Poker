"""Deterministic tests for action order, opponent policy, and action-aware EV."""

from dataclasses import replace

import pytest

from poker_trainer.engine.action_aware_simulator import calculate_action_aware_ev
from poker_trainer.engine.board_analyzer import analyze_board
from poker_trainer.engine.candidate_actions import generate_candidate_actions
from poker_trainer.engine.opponent_policy import (
    PolicyContext,
    load_opponent_profiles,
    opponent_action_distribution,
)
from poker_trainer.models import (
    ActionAwareSettings,
    ActionDistribution,
    Card,
    GameState,
    HeroActionKind,
    OpponentAction,
    OpponentProfile,
    Position,
    TablePlayer,
    TableState,
    create_default_table,
)


def cards(codes: str) -> tuple[Card, ...]:
    return tuple(Card.from_code(code) for code in codes.split())


def table(player_count: int, hero_position: Position, street: str) -> TableState:
    return create_default_table(player_count, hero_position.value, street, 500.0, 500.0)


def state(
    player_count: int = 3,
    hero_position: Position = Position.SMALL_BLIND,
    board: str = "QS 10D 4S",
    amount_to_call: float = 0.0,
    table_state: TableState | None = None,
) -> GameState:
    selected_table = table_state or table(player_count, hero_position, "flop")
    return GameState(
        active_players=player_count,
        hero_cards=cards("AS KS"),
        community_cards=cards(board),
        hero_position=hero_position,
        pot_size=120.0,
        amount_to_call=amount_to_call,
        hero_stack=500.0,
        effective_stack=500.0,
        small_blind=5.0,
        big_blind=10.0,
        requested_simulation_count=200,
        table_state=selected_table,
    )


@pytest.mark.parametrize(
    ("player_count", "street", "expected"),
    [
        (2, "preflop", (0, 1)),
        (2, "flop", (1, 0)),
        (6, "preflop", (3, 4, 5, 0, 1, 2)),
        (6, "flop", (1, 2, 3, 4, 5, 0)),
        (10, "preflop", (3, 4, 5, 6, 7, 8, 9, 0, 1, 2)),
    ],
)
def test_clockwise_action_order(player_count: int, street: str, expected: tuple[int, ...]) -> None:
    result = table(player_count, Position.BUTTON, street)

    assert result.action_order() == expected


def test_folded_and_all_in_players_are_skipped() -> None:
    original = table(6, Position.BUTTON, "flop")
    players = tuple(
        replace(player, folded=True, eligible_to_act=False)
        if player.seat == 2
        else replace(player, all_in=True, stack=0.0, eligible_to_act=False)
        if player.seat == 4
        else player
        for player in original.players
    )
    result = replace(original, players=players)

    assert result.action_order() == (1, 3, 5, 0)
    assert 2 not in result.response_order_after_hero(aggression_reopens=True)
    assert 4 not in result.response_order_after_hero(aggression_reopens=True)


def test_raise_reopens_clockwise_action() -> None:
    result = table(6, Position.BUTTON, "flop")

    assert result.reopened_order_after_raise(4) == (5, 0, 1, 2, 3)


def policy_player(profile: OpponentProfile) -> TablePlayer:
    return TablePlayer(seat=2, position="big_blind", stack=500.0, profile=profile)


def context(amount_to_call: float) -> PolicyContext:
    return PolicyContext(
        pot_size=100.0,
        amount_to_call=amount_to_call,
        minimum_raise=20.0,
        board_analysis=analyze_board(cards("QH 7D 2C")),
        opponents_remaining=1,
        position_fraction=0.5,
        prior_aggression=0,
        raises_so_far=0,
        maximum_raises=1,
    )


def test_policy_returns_only_legal_normalized_actions() -> None:
    result = opponent_action_distribution(
        policy_player(OpponentProfile.UNKNOWN_BALANCED),
        (Card.from_code("AS"), Card.from_code("AD")),
        cards("QH 7D 2C"),
        context(20.0),
    )

    assert set(result.probabilities) == {
        OpponentAction.FOLD,
        OpponentAction.CALL,
        OpponentAction.RAISE,
        OpponentAction.ALL_IN,
    }
    assert sum(result.probabilities.values()) == pytest.approx(1.0)
    assert all(0 <= value <= 1 for value in result.probabilities.values())


def test_strong_hands_continue_more_than_air() -> None:
    player = policy_player(OpponentProfile.UNKNOWN_BALANCED)
    strong = opponent_action_distribution(
        player,
        (Card.from_code("QS"), Card.from_code("QD")),
        cards("QH 7D 2C"),
        context(40.0),
    )
    weak = opponent_action_distribution(
        player,
        (Card.from_code("8S"), Card.from_code("3D")),
        cards("QH 7D 2C"),
        context(40.0),
    )

    assert strong.probabilities[OpponentAction.FOLD] < weak.probabilities[OpponentAction.FOLD]


def test_larger_bets_create_more_folds() -> None:
    player = policy_player(OpponentProfile.UNKNOWN_BALANCED)
    hole = (Card.from_code("JC"), Card.from_code("9C"))
    small = opponent_action_distribution(player, hole, cards("QH 7D 2C"), context(20.0))
    large = opponent_action_distribution(player, hole, cards("QH 7D 2C"), context(100.0))

    assert large.probabilities[OpponentAction.FOLD] > small.probabilities[OpponentAction.FOLD]


def test_loose_profiles_continue_and_aggressive_profiles_raise_more() -> None:
    hole = (Card.from_code("QH"), Card.from_code("JD"))
    board = cards("QS 7D 2C")
    tight = opponent_action_distribution(
        policy_player(OpponentProfile.TIGHT_PASSIVE), hole, board, context(35.0)
    )
    loose = opponent_action_distribution(
        policy_player(OpponentProfile.LOOSE_PASSIVE), hole, board, context(35.0)
    )
    passive = opponent_action_distribution(
        policy_player(OpponentProfile.TIGHT_PASSIVE), hole, board, context(35.0)
    )
    aggressive = opponent_action_distribution(
        policy_player(OpponentProfile.TIGHT_AGGRESSIVE), hole, board, context(35.0)
    )

    assert loose.probabilities[OpponentAction.FOLD] < tight.probabilities[OpponentAction.FOLD]
    assert (
        aggressive.probabilities[OpponentAction.RAISE] > passive.probabilities[OpponentAction.RAISE]
    )
    assert set(load_opponent_profiles()) == set(OpponentProfile)


def _forced_policy(
    _player: TablePlayer,
    _hole: tuple[Card, Card],
    _board: tuple[Card, ...],
    policy_context: PolicyContext,
    *,
    fold: bool,
) -> ActionDistribution:
    if policy_context.amount_to_call <= 0:
        action = OpponentAction.CHECK
    else:
        action = OpponentAction.FOLD if fold else OpponentAction.CALL
    return ActionDistribution(probabilities={action: 1.0}, explanation=("test policy",))


def force_fold(
    player: TablePlayer,
    hole: tuple[Card, Card],
    board: tuple[Card, ...],
    policy_context: PolicyContext,
) -> ActionDistribution:
    return _forced_policy(player, hole, board, policy_context, fold=True)


def force_call(
    player: TablePlayer,
    hole: tuple[Card, Card],
    board: tuple[Card, ...],
    policy_context: PolicyContext,
) -> ActionDistribution:
    return _forced_policy(player, hole, board, policy_context, fold=False)


def quick(simulations: int = 200) -> ActionAwareSettings:
    return ActionAwareSettings(simulations_per_action=simulations, maximum_raises_per_street=1)


def test_candidate_actions_cover_checked_to_and_facing_bet() -> None:
    checked = generate_candidate_actions(state())
    facing = generate_candidate_actions(state(amount_to_call=30.0))

    assert checked[0].kind is HeroActionKind.CHECK
    assert {candidate.label for candidate in checked} >= {
        "Bet 25% pot",
        "Bet 100% pot",
        "All-in",
    }
    assert {candidate.kind for candidate in facing} >= {
        HeroActionKind.FOLD,
        HeroActionKind.CALL,
        HeroActionKind.RAISE,
        HeroActionKind.ALL_IN,
    }
    assert len({candidate.additional_investment for candidate in facing[2:]}) == len(facing[2:])


def test_all_opponents_folding_awards_current_pot_without_double_counting_bet() -> None:
    game_state = state()
    result = calculate_action_aware_ev(game_state, quick(50), seed=1, policy_callback=force_fold)
    bet = next(item for item in result.action_results if item.candidate.label == "Bet 50% pot")

    assert bet.immediate_fold_probability == 1.0
    assert bet.continue_probability == 0.0
    assert bet.estimated_net_ev == game_state.pot_size
    assert bet.average_hero_investment == pytest.approx(game_state.pot_size * 0.50)


def test_fold_has_zero_future_ev_and_investments_are_stack_capped() -> None:
    game_state = state(amount_to_call=30.0)
    result = calculate_action_aware_ev(game_state, quick(50), seed=2)
    fold = next(
        item for item in result.action_results if item.candidate.kind is HeroActionKind.FOLD
    )

    assert fold.estimated_net_ev == 0.0
    assert all(
        item.average_hero_investment <= game_state.hero_stack for item in result.action_results
    )


def test_same_seed_is_reproducible_and_confidence_shrinks() -> None:
    game_state = state()
    first = calculate_action_aware_ev(game_state, quick(150), seed=33, policy_callback=force_call)
    second = calculate_action_aware_ev(game_state, quick(150), seed=33, policy_callback=force_call)
    larger = calculate_action_aware_ev(game_state, quick(900), seed=33, policy_callback=force_call)
    first_bet = next(item for item in first.action_results if item.candidate.label == "Bet 50% pot")
    second_bet = next(
        item for item in second.action_results if item.candidate.label == "Bet 50% pot"
    )
    larger_bet = next(
        item for item in larger.action_results if item.candidate.label == "Bet 50% pot"
    )

    assert first_bet == second_bet
    assert larger_bet.standard_error < first_bet.standard_error


def test_players_behind_change_action_frequencies() -> None:
    tight_table = table(6, Position.SMALL_BLIND, "flop")
    tight_players = tuple(
        replace(player, profile=OpponentProfile.TIGHT_PASSIVE) if not player.is_hero else player
        for player in tight_table.players
    )
    loose_players = tuple(
        replace(player, profile=OpponentProfile.LOOSE_AGGRESSIVE) if not player.is_hero else player
        for player in tight_table.players
    )
    tight_result = calculate_action_aware_ev(
        state(6, Position.SMALL_BLIND, table_state=replace(tight_table, players=tight_players)),
        quick(300),
        seed=9,
    )
    loose_result = calculate_action_aware_ev(
        state(6, Position.SMALL_BLIND, table_state=replace(tight_table, players=loose_players)),
        quick(300),
        seed=9,
    )
    tight_bet = next(
        item for item in tight_result.action_results if item.candidate.label == "Bet 50% pot"
    )
    loose_bet = next(
        item for item in loose_result.action_results if item.candidate.label == "Bet 50% pot"
    )

    assert tight_bet.immediate_fold_probability > loose_bet.immediate_fold_probability
    assert tight_bet.facing_raise_probability < loose_bet.facing_raise_probability


def test_hero_last_to_act_has_no_later_responses_after_check() -> None:
    last_table = table(6, Position.BUTTON, "flop")

    assert not last_table.players_after_hero()
    result = calculate_action_aware_ev(
        state(6, Position.BUTTON, table_state=last_table), quick(100), seed=4
    )
    check = next(
        item for item in result.action_results if item.candidate.kind is HeroActionKind.CHECK
    )
    assert check.facing_raise_probability == 0.0
