"""Small exact probability benchmark helpers."""

from __future__ import annotations

from time import perf_counter

from poker_trainer.engine.probability_calculator import calculate_final_hand_probabilities
from poker_trainer.models.card import Card
from poker_trainer.models.game_state import GameState, Position


def _cards(codes: str) -> tuple[Card, ...]:
    return tuple(Card.from_code(code) for code in codes.split())


def benchmark_turn_probability() -> float:
    """Return elapsed seconds for a representative turn probability calculation."""
    state = GameState(
        active_players=2,
        hero_cards=_cards("AS KS"),
        community_cards=_cards("QS 7S 2C 3D"),
        hero_position=Position.BUTTON,
    )
    start = perf_counter()
    calculate_final_hand_probabilities(state)
    return perf_counter() - start


def benchmark_flop_probability() -> float:
    """Return elapsed seconds for a representative flop probability calculation."""
    state = GameState(
        active_players=2,
        hero_cards=_cards("AS KS"),
        community_cards=_cards("QS 7S 2C"),
        hero_position=Position.BUTTON,
    )
    start = perf_counter()
    calculate_final_hand_probabilities(state)
    return perf_counter() - start


if __name__ == "__main__":
    print(f"Turn exact probability: {benchmark_turn_probability():.4f}s")
    print(f"Flop exact probability: {benchmark_flop_probability():.4f}s")
