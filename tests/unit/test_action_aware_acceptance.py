"""Named acceptance scenarios for players acting behind the hero."""

from dataclasses import replace

import pytest

from poker_trainer.engine.action_aware_simulator import calculate_action_aware_ev
from poker_trainer.engine.equity_calculator import calculate_equity
from poker_trainer.models import (
    ActionAwareSettings,
    Card,
    GameState,
    HeroActionKind,
    OpponentProfile,
    Position,
    TableState,
    create_default_table,
)


def cards(codes: str) -> tuple[Card, ...]:
    return tuple(Card.from_code(code) for code in codes.split())


def settings(simulations: int) -> ActionAwareSettings:
    return ActionAwareSettings(simulations_per_action=simulations, maximum_raises_per_street=1)


def game_state(
    table: TableState,
    *,
    hero_cards: str = "AS KS",
    board: str = "QS 10D 4S",
    pot: float = 120.0,
    amount_to_call: float = 0.0,
    stack: float = 500.0,
) -> GameState:
    return GameState(
        active_players=len(table.players),
        hero_cards=cards(hero_cards),
        community_cards=cards(board),
        hero_position=Position(table.hero.position),
        pot_size=pot,
        amount_to_call=amount_to_call,
        hero_stack=stack,
        effective_stack=stack,
        small_blind=5.0,
        big_blind=10.0,
        table_state=table,
    )


def test_scenario_a_hero_last_to_act_matches_heads_up_showdown_equity() -> None:
    base = create_default_table(2, Position.BUTTON.value, "river", 500.0, 500.0)
    players = tuple(
        replace(
            player,
            profile=OpponentProfile.CUSTOM,
            range_text="random",
            previous_actions=("Bet 30",),
            acted_this_round=True,
            round_contribution=30.0,
            total_contribution=30.0,
        )
        if not player.is_hero
        else player
        for player in base.players
    )
    scenario = game_state(
        replace(base, players=players),
        board="QS 10D 4S 2C 3H",
        amount_to_call=30.0,
    )

    action_aware = calculate_action_aware_ev(scenario, settings(1_000), seed=31)
    raw = calculate_equity(scenario, simulation_count=1_000, seed=31)
    call = next(
        result
        for result in action_aware.action_results
        if result.candidate.kind is HeroActionKind.CALL
    )

    assert not scenario.table_state.players_after_hero()
    assert call.facing_raise_probability == 0.0
    assert call.conditional_showdown_equity == pytest.approx(raw.total_equity, abs=0.06)


def test_scenario_b_strong_draw_bet_models_all_response_branches() -> None:
    table = create_default_table(4, Position.SMALL_BLIND.value, "flop", 500.0, 500.0)
    scenario = game_state(table)

    result = calculate_action_aware_ev(scenario, settings(500), seed=41)
    bet = next(item for item in result.action_results if item.candidate.key == "bet_50")

    assert len(table.players_after_hero()) == 3
    assert 0.0 < bet.immediate_fold_probability < 1.0
    assert 0.0 < bet.exactly_one_continues_probability < 1.0
    assert 0.0 < bet.multiple_continue_probability < 1.0
    assert 0.0 < bet.facing_raise_probability < 1.0


def test_scenario_c_prior_bettor_and_two_players_behind_are_modeled() -> None:
    base = create_default_table(6, Position.HIJACK.value, "flop", 500.0, 500.0)
    players = []
    for player in base.players:
        if player.is_hero:
            players.append(player)
        elif player.position == Position.UNDER_THE_GUN.value:
            players.append(
                replace(
                    player,
                    previous_actions=("Bet 30",),
                    acted_this_round=True,
                    round_contribution=30.0,
                    total_contribution=30.0,
                )
            )
        elif player.position in {
            Position.SMALL_BLIND.value,
            Position.BIG_BLIND.value,
        }:
            players.append(replace(player, folded=True, eligible_to_act=False))
        else:
            players.append(player)
    table = replace(base, players=tuple(players))
    scenario = game_state(table, amount_to_call=30.0)

    result = calculate_action_aware_ev(scenario, settings(500), seed=52)
    call = next(
        item for item in result.action_results if item.candidate.kind is HeroActionKind.CALL
    )

    assert tuple(player.position for player in table.players_after_hero()) == (
        Position.CUTOFF.value,
        Position.BUTTON.value,
    )
    assert call.exactly_one_continues_probability > 0.0
    assert call.multiple_continue_probability > 0.0
    assert call.facing_raise_probability > 0.0
    assert call.showdown_probability < 1.0


def test_scenario_d_profiles_change_frequencies_and_recommendation() -> None:
    base = create_default_table(3, Position.SMALL_BLIND.value, "flop", 200.0, 200.0)

    def analyze(profile: OpponentProfile):
        players = tuple(
            replace(player, profile=profile) if not player.is_hero else player
            for player in base.players
        )
        scenario = game_state(
            replace(base, players=players),
            hero_cards="7C 2D",
            board="AS KD 9H",
            pot=60.0,
            stack=200.0,
        )
        return calculate_action_aware_ev(scenario, settings(300), seed=19)

    tight = analyze(OpponentProfile.TIGHT_PASSIVE)
    loose_aggressive = analyze(OpponentProfile.LOOSE_AGGRESSIVE)
    tight_bet = next(item for item in tight.action_results if item.candidate.key == "bet_50")
    loose_bet = next(
        item for item in loose_aggressive.action_results if item.candidate.key == "bet_50"
    )

    assert tight_bet.immediate_fold_probability > loose_bet.immediate_fold_probability
    assert tight_bet.facing_raise_probability < loose_bet.facing_raise_probability
    assert tight.recommended_action != loose_aggressive.recommended_action


def test_adding_two_players_behind_changes_the_recommendation() -> None:
    base = create_default_table(6, Position.HIJACK.value, "flop", 200.0, 200.0)

    def analyze(players_behind: int):
        players = []
        for player in base.players:
            if player.is_hero:
                players.append(player)
            elif player.position == Position.UNDER_THE_GUN.value:
                players.append(
                    replace(
                        player,
                        profile=OpponentProfile.LOOSE_AGGRESSIVE,
                        previous_actions=("Bet 30",),
                        acted_this_round=True,
                        round_contribution=30.0,
                        total_contribution=30.0,
                    )
                )
            elif players_behind == 2 and player.position in {
                Position.CUTOFF.value,
                Position.BUTTON.value,
            }:
                players.append(
                    replace(
                        player,
                        profile=OpponentProfile.LOOSE_AGGRESSIVE,
                        acted_this_round=False,
                        previous_actions=(),
                    )
                )
            else:
                players.append(replace(player, folded=True, eligible_to_act=False))
        scenario = game_state(
            replace(base, players=tuple(players)),
            hero_cards="7C 2D",
            board="AS KD 9H",
            pot=60.0,
            amount_to_call=30.0,
            stack=200.0,
        )
        return calculate_action_aware_ev(scenario, settings(250), seed=44)

    hero_last = analyze(0)
    two_behind = analyze(2)

    assert hero_last.recommended_action == "Raise to 60 chips"
    assert two_behind.recommended_action == "Fold"
