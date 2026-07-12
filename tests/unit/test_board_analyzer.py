"""Tests for board texture analysis."""

from poker_trainer.engine.board_analyzer import (
    OverallTexture,
    PairingTexture,
    StraightTexture,
    SuitTexture,
    analyze_board,
)
from poker_trainer.models import Card


def cards(codes: str) -> tuple[Card, ...]:
    """Create cards from a whitespace-separated code list."""
    return tuple(Card.from_code(code) for code in codes.split())


def test_dry_rainbow_flop() -> None:
    analysis = analyze_board(cards("AS 7D 2C"))

    assert analysis.pairing is PairingTexture.UNPAIRED
    assert analysis.suit_texture is SuitTexture.RAINBOW
    assert analysis.overall_texture is OverallTexture.DRY


def test_two_tone_flop() -> None:
    assert analyze_board(cards("AS 7S 2C")).suit_texture is SuitTexture.TWO_TONE


def test_monotone_flop() -> None:
    assert analyze_board(cards("AS 7S 2S")).suit_texture is SuitTexture.MONOTONE


def test_paired_board() -> None:
    assert analyze_board(cards("AS AD 2C")).pairing is PairingTexture.PAIRED


def test_double_paired_river() -> None:
    assert analyze_board(cards("AS AD 2C 2H 9S")).pairing is PairingTexture.DOUBLE_PAIRED


def test_trips_board() -> None:
    assert analyze_board(cards("AS AD AC 2H 9S")).pairing is PairingTexture.TRIPS


def test_connected_board() -> None:
    analysis = analyze_board(cards("8S 7D 6C"))

    assert analysis.straight_texture is StraightTexture.THREE_CARD_SEQUENCE
    assert analysis.overall_texture is not OverallTexture.DRY


def test_four_card_straight_board() -> None:
    assert (
        analyze_board(cards("8S 7D 6C 5H")).straight_texture
        is StraightTexture.ONE_CARD_STRAIGHT_POSSIBLE
    )


def test_straight_completed_on_board() -> None:
    assert (
        analyze_board(cards("8S 7D 6C 5H 4S")).straight_texture
        is StraightTexture.COMPLETED_STRAIGHT_ON_BOARD
    )


def test_ace_low_connectivity() -> None:
    assert (
        analyze_board(cards("AS 2D 3C 9H")).straight_texture is StraightTexture.THREE_CARD_SEQUENCE
    )
