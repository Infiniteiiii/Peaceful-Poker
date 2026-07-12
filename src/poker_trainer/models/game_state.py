"""Validated Texas Hold'em game-state models."""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import Enum

from poker_trainer.models.action_aware import TableState, create_default_table
from poker_trainer.models.card import Card
from poker_trainer.utils.exceptions import (
    DuplicateCardError,
    InvalidBetError,
    InvalidBoardLengthError,
    InvalidGameStateError,
)


class Street(Enum):
    """Texas Hold'em streets derived from the number of community cards."""

    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"

    @property
    def display_name(self) -> str:
        """Return a user-facing street name."""
        return self.value.title()


class Position(Enum):
    """Common No-Limit Texas Hold'em table positions."""

    SMALL_BLIND = "small_blind"
    BIG_BLIND = "big_blind"
    UNDER_THE_GUN = "under_the_gun"
    UNDER_THE_GUN_PLUS_ONE = "under_the_gun_plus_one"
    MIDDLE_POSITION = "middle_position"
    LOJACK = "lojack"
    HIJACK = "hijack"
    CUTOFF = "cutoff"
    BUTTON = "button"

    @property
    def display_name(self) -> str:
        """Return a user-facing position name."""
        return {
            Position.SMALL_BLIND: "Small Blind",
            Position.BIG_BLIND: "Big Blind",
            Position.UNDER_THE_GUN: "Under the Gun",
            Position.UNDER_THE_GUN_PLUS_ONE: "Under the Gun +1",
            Position.MIDDLE_POSITION: "Middle Position",
            Position.LOJACK: "Lojack",
            Position.HIJACK: "Hijack",
            Position.CUTOFF: "Cutoff",
            Position.BUTTON: "Button",
        }[self]


@dataclass(frozen=True, slots=True)
class GameState:
    """Validated state for one Peaceful Poker Hold'em analysis request."""

    active_players: int
    hero_cards: Sequence[Card]
    community_cards: Sequence[Card] = ()
    hero_position: Position = Position.BUTTON
    pot_size: float = 0.0
    amount_to_call: float = 0.0
    hero_stack: float = 0.0
    effective_stack: float = 0.0
    small_blind: float = 0.0
    big_blind: float = 0.0
    ante: float = 0.0
    previous_action: str | None = None
    requested_simulation_count: int = 25_000
    table_state: TableState | None = None

    def __post_init__(self) -> None:
        """Normalize immutable card collections and validate the state."""
        hero_cards = tuple(self.hero_cards)
        community_cards = tuple(self.community_cards)
        object.__setattr__(self, "hero_cards", hero_cards)
        object.__setattr__(self, "community_cards", community_cards)

        if not 2 <= self.active_players <= 10:
            raise InvalidGameStateError("Active players must be from 2 through 10.")
        if len(hero_cards) != 2:
            raise InvalidGameStateError("Exactly two hero cards are required.")
        if len(community_cards) not in {0, 3, 4, 5}:
            raise InvalidBoardLengthError(
                "Community cards must contain 0, 3, 4, or 5 cards for a valid street."
            )

        known_cards = (*hero_cards, *community_cards)
        if len(set(known_cards)) != len(known_cards):
            raise DuplicateCardError("Known cards cannot contain duplicates.")

        self._validate_nonnegative("pot size", self.pot_size)
        self._validate_nonnegative("amount to call", self.amount_to_call)
        self._validate_nonnegative("hero stack", self.hero_stack)
        self._validate_nonnegative("effective stack", self.effective_stack)
        self._validate_nonnegative("small blind", self.small_blind)
        self._validate_nonnegative("big blind", self.big_blind)
        self._validate_nonnegative("ante", self.ante)
        if self.small_blind > 0 and self.big_blind > 0 and self.small_blind > self.big_blind:
            raise InvalidBetError("Small blind cannot exceed the big blind.")
        if self.amount_to_call > self.hero_stack:
            raise InvalidBetError("Amount to call cannot exceed the hero stack.")
        if self.requested_simulation_count <= 0:
            raise InvalidGameStateError("Requested simulation count must be positive.")
        table_state = self.table_state
        if table_state is None:
            table_state = create_default_table(
                self.active_players,
                self.hero_position.value,
                self.street.value,
                self.hero_stack,
                self.effective_stack or self.hero_stack,
            )
            object.__setattr__(self, "table_state", table_state)
        dealt_in_count = sum(1 for player in table_state.players if player.dealt_in)
        if dealt_in_count != self.active_players:
            raise InvalidGameStateError("Dealt-in table seats must match active players.")
        if table_state.street != self.street.value:
            table_state = replace(table_state, street=self.street.value)
            object.__setattr__(self, "table_state", table_state)

    @property
    def street(self) -> Street:
        """Derive the street from the number of community cards."""
        return street_from_board_length(len(self.community_cards))

    @property
    def known_cards(self) -> tuple[Card, ...]:
        """Return all currently known cards."""
        return (*self.hero_cards, *self.community_cards)

    @staticmethod
    def _validate_nonnegative(label: str, value: float) -> None:
        if value < 0:
            raise InvalidBetError(f"The {label} cannot be negative.")


def street_from_board_length(board_length: int) -> Street:
    """Return the Hold'em street represented by a community-card count."""
    if board_length == 0:
        return Street.PREFLOP
    if board_length == 3:
        return Street.FLOP
    if board_length == 4:
        return Street.TURN
    if board_length == 5:
        return Street.RIVER
    raise InvalidBoardLengthError("Board length must be 0, 3, 4, or 5.")
