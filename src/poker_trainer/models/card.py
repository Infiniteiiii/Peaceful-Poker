"""Card model and parsing utilities."""

from dataclasses import dataclass
from enum import Enum, IntEnum

from poker_trainer.utils.exceptions import InvalidCardError


class Suit(Enum):
    """The four suits in a standard deck."""

    SPADES = ("S", "Spades")
    HEARTS = ("H", "Hearts")
    DIAMONDS = ("D", "Diamonds")
    CLUBS = ("C", "Clubs")

    def __init__(self, code: str, display_name: str) -> None:
        self.code = code
        self.display_name = display_name

    @classmethod
    def from_code(cls, code: str) -> "Suit":
        """Return a suit from a one-letter card code."""
        normalized = code.strip().upper()
        for suit in cls:
            if suit.code == normalized:
                return suit
        raise InvalidCardError(f"Unknown suit code: {code!r}. Use S, H, D, or C.")


class Rank(IntEnum):
    """Card ranks ordered by poker strength."""

    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    ACE = 14

    @property
    def code(self) -> str:
        """Return the compact rank code used in card strings."""
        return {
            Rank.TEN: "10",
            Rank.JACK: "J",
            Rank.QUEEN: "Q",
            Rank.KING: "K",
            Rank.ACE: "A",
        }.get(self, str(int(self)))

    @property
    def short_code(self) -> str:
        """Return a one-character rank code where ten is represented as T."""
        return "T" if self is Rank.TEN else self.code

    @property
    def display_name(self) -> str:
        """Return the display name for the rank."""
        return {
            Rank.TWO: "Two",
            Rank.THREE: "Three",
            Rank.FOUR: "Four",
            Rank.FIVE: "Five",
            Rank.SIX: "Six",
            Rank.SEVEN: "Seven",
            Rank.EIGHT: "Eight",
            Rank.NINE: "Nine",
            Rank.TEN: "Ten",
            Rank.JACK: "Jack",
            Rank.QUEEN: "Queen",
            Rank.KING: "King",
            Rank.ACE: "Ace",
        }[self]

    @property
    def plural_name(self) -> str:
        """Return a pluralized display name for grouped ranks."""
        return {
            Rank.TWO: "Twos",
            Rank.THREE: "Threes",
            Rank.FOUR: "Fours",
            Rank.FIVE: "Fives",
            Rank.SIX: "Sixes",
            Rank.SEVEN: "Sevens",
            Rank.EIGHT: "Eights",
            Rank.NINE: "Nines",
            Rank.TEN: "Tens",
            Rank.JACK: "Jacks",
            Rank.QUEEN: "Queens",
            Rank.KING: "Kings",
            Rank.ACE: "Aces",
        }[self]

    @classmethod
    def from_code(cls, code: str) -> "Rank":
        """Return a rank from a card code segment."""
        normalized = code.strip().upper()
        aliases = {
            "T": cls.TEN,
            "10": cls.TEN,
            "J": cls.JACK,
            "Q": cls.QUEEN,
            "K": cls.KING,
            "A": cls.ACE,
        }
        if normalized in aliases:
            return aliases[normalized]
        if normalized.isdigit():
            value = int(normalized)
            if 2 <= value <= 9:
                return cls(value)
        raise InvalidCardError(f"Unknown rank code: {code!r}. Use 2-10, J, Q, K, or A.")


@dataclass(frozen=True, slots=True)
class Card:
    """A single playing card."""

    rank: Rank
    suit: Suit

    @property
    def code(self) -> str:
        """Return the canonical card code, such as AS or 10H."""
        return f"{self.rank.code}{self.suit.code}"

    @property
    def short_code(self) -> str:
        """Return a compact card code, such as AS or TH."""
        return f"{self.rank.short_code}{self.suit.code}"

    @property
    def display_name(self) -> str:
        """Return a human-readable card name."""
        return f"{self.rank.display_name} of {self.suit.display_name}"

    @property
    def rank_value(self) -> int:
        """Return the numeric poker value for the card rank."""
        return int(self.rank)

    @classmethod
    def from_code(cls, code: str) -> "Card":
        """Parse a card from a short code such as AS, 10H, or td."""
        normalized = code.strip().upper()
        if len(normalized) < 2:
            raise InvalidCardError(f"Invalid card code: {code!r}.")

        suit = Suit.from_code(normalized[-1])
        rank = Rank.from_code(normalized[:-1])
        return cls(rank=rank, suit=suit)

    def __str__(self) -> str:
        """Return the canonical card code."""
        return self.code
