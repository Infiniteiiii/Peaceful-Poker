"""Evaluated poker hand data structures."""

from dataclasses import dataclass
from enum import IntEnum

from poker_trainer.models.card import Card


class HandCategory(IntEnum):
    """Poker hand categories ordered from weakest to strongest."""

    HIGH_CARD = 0
    PAIR = 1
    TWO_PAIR = 2
    THREE_OF_A_KIND = 3
    STRAIGHT = 4
    FLUSH = 5
    FULL_HOUSE = 6
    FOUR_OF_A_KIND = 7
    STRAIGHT_FLUSH = 8

    @property
    def display_name(self) -> str:
        """Return a user-facing category label."""
        return {
            HandCategory.HIGH_CARD: "High Card",
            HandCategory.PAIR: "One Pair",
            HandCategory.TWO_PAIR: "Two Pair",
            HandCategory.THREE_OF_A_KIND: "Three of a Kind",
            HandCategory.STRAIGHT: "Straight",
            HandCategory.FLUSH: "Flush",
            HandCategory.FULL_HOUSE: "Full House",
            HandCategory.FOUR_OF_A_KIND: "Four of a Kind",
            HandCategory.STRAIGHT_FLUSH: "Straight Flush",
        }[self]


@dataclass(frozen=True, slots=True)
class EvaluatedHand:
    """The result of evaluating a poker hand."""

    category: HandCategory
    tie_breakers: tuple[int, ...]
    cards: tuple[Card, ...]
    description: str

    @property
    def score(self) -> tuple[int, tuple[int, ...]]:
        """Return a comparable score for the hand."""
        return (int(self.category), self.tie_breakers)

    @property
    def is_royal_flush(self) -> bool:
        """Return whether this hand is an ace-high straight flush."""
        return self.category is HandCategory.STRAIGHT_FLUSH and self.tie_breakers == (14,)

    @property
    def display_category(self) -> str:
        """Return the display category, naming royal flushes explicitly."""
        return "Royal Flush" if self.is_royal_flush else self.category.display_name

    def __lt__(self, other: object) -> bool:
        """Compare hands by poker strength."""
        if not isinstance(other, EvaluatedHand):
            return NotImplemented
        return self.score < other.score

    def __le__(self, other: object) -> bool:
        """Compare hands by poker strength."""
        if not isinstance(other, EvaluatedHand):
            return NotImplemented
        return self.score <= other.score

    def __gt__(self, other: object) -> bool:
        """Compare hands by poker strength."""
        if not isinstance(other, EvaluatedHand):
            return NotImplemented
        return self.score > other.score

    def __ge__(self, other: object) -> bool:
        """Compare hands by poker strength."""
        if not isinstance(other, EvaluatedHand):
            return NotImplemented
        return self.score >= other.score
