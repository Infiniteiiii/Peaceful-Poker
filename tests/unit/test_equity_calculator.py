"""Tests for exact and Monte Carlo equity."""

import pytest

from poker_trainer.engine.equity_calculator import calculate_equity
from poker_trainer.engine.range_parser import available_combinations, filter_combinations
from poker_trainer.models import Card, GameState, Position
from poker_trainer.utils.exceptions import SimulationCancelledError, UnsupportedRangeError


def cards(codes: str) -> tuple[Card, ...]:
    return tuple(Card.from_code(code) for code in codes.split())


def state(hero: str, board: str, players: int = 2) -> GameState:
    return GameState(
        active_players=players,
        hero_cards=cards(hero),
        community_cards=cards(board),
        hero_position=Position.BUTTON,
        requested_simulation_count=1_000,
    )


def test_guaranteed_hero_win_with_known_opponent() -> None:
    result = calculate_equity(
        state("AS KS", "QS JS 10S 2D 3C"),
        known_opponent_hands=(cards("9H 9C"),),
    )

    assert result.calculation_method == "exact_enumeration"
    assert result.wins == 1
    assert result.total_equity == 1.0


def test_guaranteed_hero_loss_with_known_opponent() -> None:
    result = calculate_equity(
        state("2H 3C", "AS KS QS JS 9D"),
        known_opponent_hands=(cards("10S 8C"),),
    )

    assert result.losses == 1
    assert result.total_equity == 0.0


def test_board_only_split_pot() -> None:
    result = calculate_equity(
        state("AS KD", "2S 3D 4C 5H 6S"),
        known_opponent_hands=(cards("QH JD"),),
    )

    assert result.ties == 1
    assert result.pot_share_total == 0.5
    assert result.total_equity == 0.5


def test_multiway_fractional_split() -> None:
    result = calculate_equity(
        state("AS KD", "2S 3D 4C 5H 6S", players=3),
        known_opponent_hands=(cards("QH JD"), cards("9C 8D")),
    )

    assert result.ties == 1
    assert result.pot_share_total == pytest.approx(1 / 3)


def test_exact_river_random_opponent_excludes_known_cards() -> None:
    result = calculate_equity(state("AS KS", "QS JS 10S 2D 3C"))

    assert result.iterations == 990
    assert result.total_equity == 1.0


def test_exact_heads_up_turn_supported() -> None:
    result = calculate_equity(state("AS KS", "QS JS 10S 2D"))

    assert result.calculation_method == "exact_enumeration"
    assert result.iterations > 40_000


def test_monte_carlo_seed_reproducible() -> None:
    game_state = state("AS KS", "QS 7S 2C", players=6)
    first = calculate_equity(game_state, simulation_count=500, seed=42)
    second = calculate_equity(game_state, simulation_count=500, seed=42)

    assert first.total_equity == second.total_equity
    assert first.win_percentage == second.win_percentage


def test_ten_player_simulation_runs() -> None:
    result = calculate_equity(state("AS KS", "QS 7S 2C", players=10), simulation_count=100, seed=1)

    assert result.iterations == 100
    assert 0.0 <= result.total_equity <= 1.0


def test_cancellation_raises() -> None:
    with pytest.raises(SimulationCancelledError):
        calculate_equity(
            state("AS KS", "QS 7S 2C", players=6),
            simulation_count=100,
            cancel_callback=lambda: True,
        )


def test_invalid_range_rejected() -> None:
    combos = available_combinations(cards("AS AH KS KH QS QH"))

    with pytest.raises(UnsupportedRangeError):
        filter_combinations(combos, "not-a-range")


def test_range_presets_and_notation_return_legal_combinations() -> None:
    combos = available_combinations(cards("AS AH KS KH QS QH 9S 9H"))

    assert filter_combinations(combos, "premium")
    assert all(
        all(card in {c for combo in combos for c in combo} for card in combo)
        for combo in filter_combinations(combos, "AA")
    )
    assert filter_combinations(combos, "99+")
    assert filter_combinations(combos, "AKs")
    assert filter_combinations(combos, "22-99")
