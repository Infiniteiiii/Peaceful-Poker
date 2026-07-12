"""Educational board texture analysis."""

from collections import Counter
from dataclasses import dataclass
from enum import Enum

from poker_trainer.engine.hand_evaluator import evaluate_best_hand
from poker_trainer.models.card import Card, Rank
from poker_trainer.models.hand import HandCategory
from poker_trainer.utils.exceptions import InvalidBoardLengthError


class PairingTexture(Enum):
    """Rank pairing visible on the board."""

    NO_BOARD = "no_board"
    UNPAIRED = "unpaired"
    PAIRED = "paired"
    DOUBLE_PAIRED = "double_paired"
    TRIPS = "trips"
    FULL_HOUSE = "full_house"
    FOUR_OF_A_KIND = "four_of_a_kind"


class SuitTexture(Enum):
    """Suit distribution visible on the board."""

    NO_BOARD = "no_board"
    RAINBOW = "rainbow"
    TWO_TONE = "two_tone"
    MONOTONE = "monotone"
    FOUR_FLUSH = "four_flush"
    FIVE_FLUSH = "five_flush"


class StraightTexture(Enum):
    """Straight connectivity visible on the board."""

    NO_BOARD = "no_board"
    DISCONNECTED = "disconnected"
    MODERATELY_CONNECTED = "moderately_connected"
    HIGHLY_CONNECTED = "highly_connected"
    THREE_CARD_SEQUENCE = "three_card_sequence"
    FOUR_CARD_STRAIGHT_POSSIBLE = "four_card_straight_possible"
    ONE_CARD_STRAIGHT_POSSIBLE = "one_card_straight_possible"
    COMPLETED_STRAIGHT_ON_BOARD = "completed_straight_on_board"


class OverallTexture(Enum):
    """Conservative educational board texture label."""

    NO_BOARD = "no_board"
    DRY = "dry"
    MODERATELY_CONNECTED = "moderately_connected"
    WET = "wet"
    HIGHLY_COORDINATED = "highly_coordinated"


@dataclass(frozen=True, slots=True)
class BoardAnalysis:
    """Structured board texture analysis."""

    board: tuple[Card, ...]
    pairing: PairingTexture
    suit_texture: SuitTexture
    straight_texture: StraightTexture
    overall_texture: OverallTexture
    notes: tuple[str, ...]


def analyze_board(board: tuple[Card, ...]) -> BoardAnalysis:
    """Analyze pairing, suits, straight connectivity, and overall texture."""
    if len(board) not in {0, 3, 4, 5}:
        raise InvalidBoardLengthError("Board analysis requires 0, 3, 4, or 5 community cards.")
    if len(board) == 0:
        return BoardAnalysis(
            board=board,
            pairing=PairingTexture.NO_BOARD,
            suit_texture=SuitTexture.NO_BOARD,
            straight_texture=StraightTexture.NO_BOARD,
            overall_texture=OverallTexture.NO_BOARD,
            notes=("No community cards are available yet.",),
        )

    pairing = _pairing_texture(board)
    suit_texture = _suit_texture(board)
    straight_texture = _straight_texture(board)
    overall = _overall_texture(pairing, suit_texture, straight_texture)
    return BoardAnalysis(
        board=board,
        pairing=pairing,
        suit_texture=suit_texture,
        straight_texture=straight_texture,
        overall_texture=overall,
        notes=_notes(pairing, suit_texture, straight_texture, overall),
    )


def _pairing_texture(board: tuple[Card, ...]) -> PairingTexture:
    counts = sorted(Counter(card.rank for card in board).values(), reverse=True)
    if counts[0] == 4:
        return PairingTexture.FOUR_OF_A_KIND
    if counts == [3, 2]:
        return PairingTexture.FULL_HOUSE
    if counts[0] == 3:
        return PairingTexture.TRIPS
    if counts.count(2) == 2:
        return PairingTexture.DOUBLE_PAIRED
    if counts[0] == 2:
        return PairingTexture.PAIRED
    return PairingTexture.UNPAIRED


def _suit_texture(board: tuple[Card, ...]) -> SuitTexture:
    highest = max(Counter(card.suit for card in board).values())
    if len(board) == 3:
        if highest == 1:
            return SuitTexture.RAINBOW
        if highest == 2:
            return SuitTexture.TWO_TONE
        return SuitTexture.MONOTONE
    if highest == 5:
        return SuitTexture.FIVE_FLUSH
    if highest == 4:
        return SuitTexture.FOUR_FLUSH
    if highest == 3:
        return SuitTexture.MONOTONE
    return SuitTexture.TWO_TONE


def _straight_texture(board: tuple[Card, ...]) -> StraightTexture:
    rank_values = {card.rank_value for card in board}
    expanded = _ace_low_values(rank_values)
    if len(board) == 5 and evaluate_best_hand(board).category >= HandCategory.STRAIGHT:
        return StraightTexture.COMPLETED_STRAIGHT_ON_BOARD
    if _has_one_card_straight(rank_values):
        return StraightTexture.ONE_CARD_STRAIGHT_POSSIBLE
    if _has_consecutive_run(expanded, 4):
        return StraightTexture.FOUR_CARD_STRAIGHT_POSSIBLE
    if _has_consecutive_run(expanded, 3):
        return StraightTexture.THREE_CARD_SEQUENCE
    if _rank_span(expanded) <= 4:
        return StraightTexture.HIGHLY_CONNECTED
    if _rank_span(expanded) <= 7:
        return StraightTexture.MODERATELY_CONNECTED
    return StraightTexture.DISCONNECTED


def _overall_texture(
    pairing: PairingTexture,
    suit_texture: SuitTexture,
    straight_texture: StraightTexture,
) -> OverallTexture:
    score = 0
    if pairing in {PairingTexture.PAIRED, PairingTexture.DOUBLE_PAIRED, PairingTexture.TRIPS}:
        score += 1
    if suit_texture in {SuitTexture.MONOTONE, SuitTexture.FOUR_FLUSH, SuitTexture.FIVE_FLUSH}:
        score += 2
    elif suit_texture is SuitTexture.TWO_TONE:
        score += 1
    if straight_texture in {
        StraightTexture.FOUR_CARD_STRAIGHT_POSSIBLE,
        StraightTexture.ONE_CARD_STRAIGHT_POSSIBLE,
        StraightTexture.COMPLETED_STRAIGHT_ON_BOARD,
    }:
        score += 2
    elif straight_texture in {
        StraightTexture.THREE_CARD_SEQUENCE,
        StraightTexture.HIGHLY_CONNECTED,
        StraightTexture.MODERATELY_CONNECTED,
    }:
        score += 1
    if score >= 4:
        return OverallTexture.HIGHLY_COORDINATED
    if score == 3:
        return OverallTexture.WET
    if score in {1, 2}:
        return OverallTexture.MODERATELY_CONNECTED
    return OverallTexture.DRY


def _notes(
    pairing: PairingTexture,
    suit_texture: SuitTexture,
    straight_texture: StraightTexture,
    overall: OverallTexture,
) -> tuple[str, ...]:
    return (
        f"Pairing texture: {pairing.value}.",
        f"Suit texture: {suit_texture.value}.",
        f"Straight texture: {straight_texture.value}.",
        f"Overall texture is a conservative educational label: {overall.value}.",
    )


def _ace_low_values(rank_values: set[int]) -> set[int]:
    values = set(rank_values)
    if Rank.ACE in values:
        values.add(1)
    return values


def _has_consecutive_run(values: set[int], run_length: int) -> bool:
    for start in range(1, 15 - run_length + 1):
        if set(range(start, start + run_length)).issubset(values):
            return True
    return False


def _has_one_card_straight(rank_values: set[int]) -> bool:
    expanded = _ace_low_values(rank_values)
    for start in range(1, 11):
        window = set(range(start, start + 5))
        if len(window & expanded) >= 4:
            return True
    return False


def _rank_span(values: set[int]) -> int:
    if not values:
        return 99
    return max(values) - min(values)
