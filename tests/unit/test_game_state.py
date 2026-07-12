"""Tests for validated Texas Hold'em game states."""

import pytest

from poker_trainer.models import Card, GameState, Position, Street
from poker_trainer.utils.exceptions import (
    DuplicateCardError,
    InvalidBetError,
    InvalidBoardLengthError,
    InvalidGameStateError,
)


def cards(codes: str) -> tuple[Card, ...]:
    """Create cards from a whitespace-separated code list."""
    return tuple(Card.from_code(code) for code in codes.split())


@pytest.mark.parametrize(
    ("board", "street"),
    [
        ("", Street.PREFLOP),
        ("QS 7D 2C", Street.FLOP),
        ("QS 7D 2C 3H", Street.TURN),
        ("QS 7D 2C 3H 9S", Street.RIVER),
    ],
)
def test_valid_streets_are_derived_from_board_length(board: str, street: Street) -> None:
    state = GameState(
        active_players=6,
        hero_cards=cards("AS KH"),
        community_cards=cards(board),
        hero_position=Position.BUTTON,
    )

    assert state.street is street
    assert state.known_cards == (*cards("AS KH"), *cards(board))


@pytest.mark.parametrize("active_players", [2, 10])
def test_valid_player_count_edges(active_players: int) -> None:
    state = GameState(active_players=active_players, hero_cards=cards("AS KH"))

    assert state.active_players == active_players


@pytest.mark.parametrize("active_players", [1, 11])
def test_invalid_player_counts_raise(active_players: int) -> None:
    with pytest.raises(InvalidGameStateError):
        GameState(active_players=active_players, hero_cards=cards("AS KH"))


@pytest.mark.parametrize("hero", ["AS", "AS KH QD"])
def test_exactly_two_hero_cards_are_required(hero: str) -> None:
    with pytest.raises(InvalidGameStateError):
        GameState(active_players=2, hero_cards=cards(hero))


@pytest.mark.parametrize("board", ["QS", "QS 7D"])
def test_invalid_board_lengths_raise(board: str) -> None:
    with pytest.raises(InvalidBoardLengthError):
        GameState(active_players=2, hero_cards=cards("AS KH"), community_cards=cards(board))


def test_duplicate_known_cards_raise() -> None:
    with pytest.raises(DuplicateCardError):
        GameState(active_players=2, hero_cards=cards("AS KH"), community_cards=cards("AS 7D 2C"))


@pytest.mark.parametrize(
    "field",
    [
        "pot_size",
        "amount_to_call",
        "hero_stack",
        "effective_stack",
        "small_blind",
        "big_blind",
        "ante",
    ],
)
def test_negative_betting_values_raise(field: str) -> None:
    kwargs = {field: -1.0}

    with pytest.raises(InvalidBetError):
        GameState(active_players=2, hero_cards=cards("AS KH"), **kwargs)


def test_small_blind_cannot_exceed_big_blind() -> None:
    with pytest.raises(InvalidBetError):
        GameState(active_players=2, hero_cards=cards("AS KH"), small_blind=2.0, big_blind=1.0)


@pytest.mark.parametrize(("amount_to_call", "hero_stack"), [(50.0, 50.0), (0.0, 0.0)])
def test_amount_to_call_stack_edges(amount_to_call: float, hero_stack: float) -> None:
    state = GameState(
        active_players=2,
        hero_cards=cards("AS KH"),
        amount_to_call=amount_to_call,
        hero_stack=hero_stack,
    )

    assert state.amount_to_call == amount_to_call


def test_amount_to_call_cannot_exceed_stack() -> None:
    with pytest.raises(InvalidBetError):
        GameState(active_players=2, hero_cards=cards("AS KH"), amount_to_call=51.0, hero_stack=50.0)
