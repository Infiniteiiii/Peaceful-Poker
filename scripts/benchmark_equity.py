"""Equity benchmark helpers."""

from __future__ import annotations

from time import perf_counter

from poker_trainer.engine.current_hand import analyze_current_hand
from poker_trainer.engine.equity_calculator import calculate_equity
from poker_trainer.models.card import Card
from poker_trainer.models.game_state import GameState, Position


def _cards(codes: str) -> tuple[Card, ...]:
    return tuple(Card.from_code(code) for code in codes.split())


def _state(board: str, players: int = 2) -> GameState:
    return GameState(
        active_players=players,
        hero_cards=_cards("AS KS"),
        community_cards=_cards(board),
        hero_position=Position.BUTTON,
        requested_simulation_count=25_000,
    )


def benchmark_river_exact() -> float:
    start = perf_counter()
    calculate_equity(_state("QS JS 10S 2D 3C"))
    return perf_counter() - start


def benchmark_current_hand(repetitions: int = 10_000) -> float:
    """Return average current-hand evaluation time in milliseconds."""
    state = _state("QS JS 10S 2D 3C")
    start = perf_counter()
    for _ in range(repetitions):
        analyze_current_hand(state)
    return (perf_counter() - start) * 1_000 / repetitions


def benchmark_turn_exact() -> float:
    start = perf_counter()
    calculate_equity(_state("QS JS 10S 2D"))
    return perf_counter() - start


def benchmark_monte_carlo() -> float:
    start = perf_counter()
    calculate_equity(_state("QS JS 2C", players=6), simulation_count=25_000, seed=7)
    return perf_counter() - start


def benchmark_5k_monte_carlo() -> float:
    start = perf_counter()
    calculate_equity(_state("QS JS 2C", players=6), simulation_count=5_000, seed=7)
    return perf_counter() - start


def benchmark_multiway() -> float:
    start = perf_counter()
    calculate_equity(_state("QS 10D 4S", players=10), simulation_count=5_000, seed=7)
    return perf_counter() - start


if __name__ == "__main__":
    print(f"Current-hand evaluation: {benchmark_current_hand():.4f}ms average")
    print(f"River exact equity: {benchmark_river_exact():.4f}s")
    print(f"Turn exact equity: {benchmark_turn_exact():.4f}s")
    print(f"5,000 Monte Carlo: {benchmark_5k_monte_carlo():.4f}s")
    print(f"25,000 Monte Carlo: {benchmark_monte_carlo():.4f}s")
    print(f"Multiway simulation: {benchmark_multiway():.4f}s")
