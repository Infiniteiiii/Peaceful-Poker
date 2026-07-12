"""Standard 52-card deck model."""

import random
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from poker_trainer.models.card import Card, Rank, Suit
from poker_trainer.utils.exceptions import DuplicateCardError


@dataclass(slots=True)
class Deck:
    """A mutable standard deck that can remove known cards."""

    cards: list[Card]

    @classmethod
    def standard(cls) -> "Deck":
        """Create a full 52-card deck."""
        return cls(cards=[Card(rank, suit) for suit in Suit for rank in Rank])

    def __len__(self) -> int:
        """Return the number of cards remaining in the deck."""
        return len(self.cards)

    def __contains__(self, card: Card) -> bool:
        """Return whether the card remains in the deck."""
        return card in self.cards

    def shuffle(self, rng: random.Random | None = None) -> None:
        """Shuffle the deck in place."""
        random_source = rng or random
        random_source.shuffle(self.cards)

    def remove(self, card: Card) -> Card:
        """Remove and return one known card from the deck."""
        try:
            self.cards.remove(card)
        except ValueError as exc:
            raise DuplicateCardError(f"{card.display_name} is not available in the deck.") from exc
        return card

    def remove_many(self, cards: Iterable[Card]) -> None:
        """Remove multiple known cards while rejecting duplicate requests."""
        seen: set[Card] = set()
        for card in cards:
            if card in seen:
                raise DuplicateCardError(f"{card.display_name} was provided more than once.")
            seen.add(card)
            self.remove(card)

    def remaining(self) -> tuple[Card, ...]:
        """Return the remaining cards as an immutable tuple."""
        return tuple(self.cards)

    def draw(self, count: int = 1) -> Sequence[Card]:
        """Draw cards from the top of the deck."""
        if count < 0:
            raise ValueError("Cannot draw a negative number of cards.")
        if count > len(self.cards):
            raise ValueError("Cannot draw more cards than remain in the deck.")
        drawn = self.cards[:count]
        del self.cards[:count]
        return tuple(drawn)
