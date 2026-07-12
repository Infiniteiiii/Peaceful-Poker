"""Focused action-aware policy simulation benchmarks."""

from dataclasses import replace
from time import perf_counter

from poker_trainer.engine.action_aware_simulator import (
    action_aware_preset,
    calculate_action_aware_ev,
)
from poker_trainer.models import Card, GameState, Position, create_default_table


def _cards(codes: str) -> tuple[Card, ...]:
    return tuple(Card.from_code(code) for code in codes.split())


def _state(player_count: int, hero_position: Position, players_behind: int) -> GameState:
    table = create_default_table(
        player_count,
        hero_position.value,
        "flop",
        900.0,
        620.0,
    )
    clockwise = tuple(
        player.seat for player in table.clockwise_after(table.hero_seat) if not player.is_hero
    )
    behind = set(clockwise[:players_behind])
    players = tuple(
        replace(
            player,
            acted_this_round=player.seat not in behind,
            previous_actions=() if player.seat in behind else player.previous_actions,
        )
        if not player.is_hero
        else player
        for player in table.players
    )
    return GameState(
        active_players=player_count,
        hero_cards=_cards("AS KS"),
        community_cards=_cards("QS 10D 4S"),
        hero_position=hero_position,
        pot_size=140.0,
        amount_to_call=0.0,
        hero_stack=900.0,
        effective_stack=620.0,
        small_blind=5.0,
        big_blind=10.0,
        table_state=replace(table, players=players),
    )


def benchmark(
    player_count: int,
    hero_position: Position,
    players_behind: int,
    preset: str,
) -> float:
    start = perf_counter()
    calculate_action_aware_ev(
        _state(player_count, hero_position, players_behind),
        action_aware_preset(preset),
        seed=20260712,
    )
    return perf_counter() - start


if __name__ == "__main__":
    print(f"Hero last to act, Quick: {benchmark(6, Position.BUTTON, 0, 'Quick'):.4f}s")
    print(f"One player behind, Quick: {benchmark(6, Position.CUTOFF, 1, 'Quick'):.4f}s")
    print(f"Three players behind, Quick: {benchmark(6, Position.SMALL_BLIND, 3, 'Quick'):.4f}s")
    print(f"Ten-player table, Quick: {benchmark(10, Position.SMALL_BLIND, 5, 'Quick'):.4f}s")
    print(f"Hero last to act, Standard: {benchmark(6, Position.BUTTON, 0, 'Standard'):.4f}s")
