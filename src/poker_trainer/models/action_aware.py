"""Table, opponent, and action-aware decision models."""

from dataclasses import dataclass
from enum import Enum
from math import isclose

from poker_trainer.utils.exceptions import InvalidGameStateError


class OpponentProfile(Enum):
    """Documented opponent-behavior assumptions."""

    UNKNOWN_BALANCED = "unknown_balanced"
    TIGHT_PASSIVE = "tight_passive"
    LOOSE_PASSIVE = "loose_passive"
    TIGHT_AGGRESSIVE = "tight_aggressive"
    LOOSE_AGGRESSIVE = "loose_aggressive"
    CALLING_STATION = "calling_station"
    NIT = "nit"
    MANIAC = "maniac"
    CUSTOM = "custom"

    @property
    def display_name(self) -> str:
        return self.value.replace("_", " ").title().replace("Unknown Balanced", "Unknown/Balanced")


class OpponentAction(Enum):
    """Actions available to a simulated opponent."""

    CHECK = "check"
    BET_SMALL = "bet_small"
    BET_MEDIUM = "bet_medium"
    BET_LARGE = "bet_large"
    FOLD = "fold"
    CALL = "call"
    RAISE = "raise"
    ALL_IN = "all_in"

    @property
    def display_name(self) -> str:
        return self.value.replace("_", " ").title()


class HeroActionKind(Enum):
    """Candidate hero action families."""

    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    ALL_IN = "all_in"


class PolicySimulationMode(Enum):
    """Bounded action-tree modes."""

    FAST = "fast"
    DETAILED = "detailed"


class RelativeHandStrength(Enum):
    """Coarse current-street hand classification used by opponent policy."""

    VERY_WEAK = "very_weak"
    WEAK_SHOWDOWN_VALUE = "weak_showdown_value"
    DRAW = "draw"
    MEDIUM_MADE_HAND = "medium_made_hand"
    STRONG_MADE_HAND = "strong_made_hand"
    VERY_STRONG = "very_strong_or_nutted"


@dataclass(frozen=True, slots=True)
class TablePlayer:
    """One seat relevant to the current hand."""

    seat: int
    position: str
    is_hero: bool = False
    dealt_in: bool = True
    folded: bool = False
    all_in: bool = False
    stack: float = 0.0
    round_contribution: float = 0.0
    total_contribution: float = 0.0
    profile: OpponentProfile = OpponentProfile.UNKNOWN_BALANCED
    range_text: str = "random"
    previous_actions: tuple[str, ...] = ()
    eligible_to_act: bool = True
    acted_this_round: bool = False

    def __post_init__(self) -> None:
        if self.seat < 0:
            raise InvalidGameStateError("Seat numbers cannot be negative.")
        if self.stack < 0 or self.round_contribution < 0 or self.total_contribution < 0:
            raise InvalidGameStateError("Player stacks and contributions cannot be negative.")
        if self.round_contribution > self.total_contribution:
            raise InvalidGameStateError("Round contribution cannot exceed total contribution.")
        if self.folded and self.all_in:
            raise InvalidGameStateError("A player cannot be both folded and all-in.")
        if self.all_in and self.stack != 0:
            raise InvalidGameStateError("An all-in player must have no remaining stack.")

    @property
    def can_act(self) -> bool:
        return (
            self.dealt_in
            and not self.folded
            and not self.all_in
            and self.eligible_to_act
            and self.stack > 0
        )

    @property
    def can_reach_showdown(self) -> bool:
        return self.dealt_in and not self.folded


@dataclass(frozen=True, slots=True)
class TableState:
    """Clockwise table state for the current decision."""

    players: tuple[TablePlayer, ...]
    button_seat: int
    small_blind_seat: int
    big_blind_seat: int
    hero_seat: int
    current_actor_seat: int
    street: str

    def __post_init__(self) -> None:
        if not 2 <= len(self.players) <= 10:
            raise InvalidGameStateError("A table must contain from 2 through 10 seats.")
        seats = tuple(player.seat for player in self.players)
        if len(set(seats)) != len(seats):
            raise InvalidGameStateError("Table seat numbers must be unique.")
        required = {
            self.button_seat,
            self.small_blind_seat,
            self.big_blind_seat,
            self.hero_seat,
            self.current_actor_seat,
        }
        if not required.issubset(set(seats)):
            raise InvalidGameStateError(
                "Button, blinds, hero, and current actor must occupy seats."
            )
        heroes = [player for player in self.players if player.is_hero]
        if len(heroes) != 1 or heroes[0].seat != self.hero_seat:
            raise InvalidGameStateError("Table state must contain exactly one matching hero seat.")
        if self.street not in {"preflop", "flop", "turn", "river"}:
            raise InvalidGameStateError("Table street is invalid.")

    def player(self, seat: int) -> TablePlayer:
        """Return the player occupying a seat."""
        try:
            return next(player for player in self.players if player.seat == seat)
        except StopIteration as exc:
            raise InvalidGameStateError(f"No player occupies seat {seat}.") from exc

    @property
    def hero(self) -> TablePlayer:
        return self.player(self.hero_seat)

    @property
    def active_opponents(self) -> tuple[TablePlayer, ...]:
        return tuple(
            player for player in self.players if not player.is_hero and player.can_reach_showdown
        )

    @property
    def active_opponent_count(self) -> int:
        return len(self.active_opponents)

    def clockwise_after(self, seat: int) -> tuple[TablePlayer, ...]:
        """Return every other seat clockwise after the given seat."""
        ordered = tuple(sorted(self.players, key=lambda player: player.seat))
        index = next(i for i, player in enumerate(ordered) if player.seat == seat)
        return (*ordered[index + 1 :], *ordered[:index])

    def first_to_act_seat(self) -> int:
        """Return the correct first eligible actor for the street."""
        if len(self.players) == 2 and self.street == "preflop":
            preferred = self.button_seat
        elif self.street == "preflop":
            preferred = self._next_occupied_seat(self.big_blind_seat)
        else:
            preferred = self._next_occupied_seat(self.button_seat)
        candidates = (self.player(preferred), *self.clockwise_after(preferred))
        for player in candidates:
            if player.can_act:
                return player.seat
        raise InvalidGameStateError("No player is eligible to act.")

    def action_order(self, start_seat: int | None = None) -> tuple[int, ...]:
        """Return one clockwise pass of eligible actors."""
        start = self.first_to_act_seat() if start_seat is None else start_seat
        ordered = (self.player(start), *self.clockwise_after(start))
        return tuple(player.seat for player in ordered if player.can_act)

    def response_order_after_hero(self, *, aggression_reopens: bool) -> tuple[int, ...]:
        """Return opponents who must respond after the candidate hero action."""
        order = self.clockwise_after(self.hero_seat)
        return tuple(
            player.seat
            for player in order
            if not player.is_hero
            and player.can_act
            and (aggression_reopens or not player.acted_this_round)
        )

    def reopened_order_after_raise(self, raiser_seat: int) -> tuple[int, ...]:
        """Return previously acting players whose action is reopened by a raise."""
        return tuple(
            player.seat
            for player in self.clockwise_after(raiser_seat)
            if player.can_act and player.seat != raiser_seat
        )

    def players_after_hero(self) -> tuple[TablePlayer, ...]:
        """Return not-yet-acted opponents behind hero in clockwise order."""
        return tuple(
            player
            for player in self.clockwise_after(self.hero_seat)
            if not player.is_hero and player.can_act and not player.acted_this_round
        )

    def _next_occupied_seat(self, seat: int) -> int:
        return self.clockwise_after(seat)[0].seat


@dataclass(frozen=True, slots=True)
class PolicyProfile:
    """Numeric behavior parameters loaded from readable configuration."""

    profile: OpponentProfile
    preflop_range: str
    postflop_range: str
    fold_bias: float
    call_bias: float
    aggression: float
    reraise_frequency: float
    bluff_frequency: float
    value_raise_threshold: float
    size_sensitivity: float
    position_sensitivity: float
    stack_sensitivity: float
    board_sensitivity: float
    prior_aggression_sensitivity: float


@dataclass(frozen=True, slots=True)
class ActionDistribution:
    """Normalized probability distribution over legal opponent actions."""

    probabilities: dict[OpponentAction, float]
    explanation: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.probabilities:
            raise InvalidGameStateError("An opponent action distribution cannot be empty.")
        if any(probability < 0 or probability > 1 for probability in self.probabilities.values()):
            raise InvalidGameStateError("Opponent action probabilities must be from zero to one.")
        if not isclose(sum(self.probabilities.values()), 1.0, abs_tol=1e-9):
            raise InvalidGameStateError("Opponent action probabilities must sum to one.")


@dataclass(frozen=True, slots=True)
class HeroCandidateAction:
    """One separately evaluated legal hero action and sizing."""

    key: str
    label: str
    kind: HeroActionKind
    additional_investment: float
    target_round_contribution: float


@dataclass(frozen=True, slots=True)
class ActionAwareSettings:
    """Controls for bounded policy-tree simulation."""

    mode: PolicySimulationMode = PolicySimulationMode.FAST
    simulations_per_action: int = 2_500
    maximum_raises_per_street: int = 1
    maximum_action_depth: int = 20
    simplified_future_streets: bool = True

    def __post_init__(self) -> None:
        if self.simulations_per_action <= 0:
            raise InvalidGameStateError("Policy simulation count must be positive.")
        if self.maximum_raises_per_street < 0 or self.maximum_action_depth <= 0:
            raise InvalidGameStateError("Action-tree limits must be nonnegative and finite.")


@dataclass(frozen=True, slots=True)
class CandidateActionResult:
    """Estimated action-aware statistics for one hero action."""

    candidate: HeroCandidateAction
    estimated_net_ev: float
    standard_error: float
    confidence_interval_low: float
    confidence_interval_high: float
    immediate_fold_probability: float
    continue_probability: float
    exactly_one_continues_probability: float
    multiple_continue_probability: float
    facing_raise_probability: float
    showdown_probability: float
    conditional_showdown_equity: float
    average_final_pot: float
    average_hero_investment: float
    simulations: int
    assumptions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ActionAwareResult:
    """Per-action EV estimates kept separate from raw showdown equity."""

    action_results: tuple[CandidateActionResult, ...]
    recommended_action: str
    uncertainty_note: str | None
    simulations_per_action: int
    random_seed: int | None
    execution_time: float
    assumptions: tuple[str, ...]


def create_default_table(
    active_players: int,
    hero_position: str,
    street: str,
    hero_stack: float,
    opponent_stack: float,
) -> TableState:
    """Create a practical clockwise table for legacy and quick-entry states."""
    positions = _positions_for_count(active_players)
    hero_seat = next(
        (seat for seat, position in enumerate(positions) if position == hero_position),
        0,
    )
    button = positions.index("button")
    small_blind = button if active_players == 2 else positions.index("small_blind")
    big_blind = positions.index("big_blind")
    if active_players == 2 and street == "preflop":
        first_to_act = button
    elif street == "preflop":
        first_to_act = (big_blind + 1) % active_players
    else:
        first_to_act = (button + 1) % active_players
    action_order = tuple(
        (first_to_act + offset) % active_players for offset in range(active_players)
    )
    hero_index = action_order.index(hero_seat)
    acted_before_hero = set(action_order[:hero_index])
    players = tuple(
        TablePlayer(
            seat=seat,
            position=position,
            is_hero=seat == hero_seat,
            stack=hero_stack if seat == hero_seat else opponent_stack,
            profile=OpponentProfile.UNKNOWN_BALANCED,
            range_text="random",
            previous_actions=("Checked",) if seat in acted_before_hero else (),
            acted_this_round=seat in acted_before_hero,
        )
        for seat, position in enumerate(positions)
    )
    return TableState(
        players=players,
        button_seat=button,
        small_blind_seat=small_blind,
        big_blind_seat=big_blind,
        hero_seat=hero_seat,
        current_actor_seat=hero_seat,
        street=street,
    )


def _positions_for_count(player_count: int) -> tuple[str, ...]:
    if not 2 <= player_count <= 10:
        raise InvalidGameStateError("Active players must be from 2 through 10.")
    if player_count == 2:
        return ("button", "big_blind")
    by_count = {
        3: ("button", "small_blind", "big_blind"),
        4: ("button", "small_blind", "big_blind", "under_the_gun"),
        5: ("button", "small_blind", "big_blind", "under_the_gun", "cutoff"),
        6: ("button", "small_blind", "big_blind", "under_the_gun", "hijack", "cutoff"),
        7: (
            "button",
            "small_blind",
            "big_blind",
            "under_the_gun",
            "middle_position",
            "hijack",
            "cutoff",
        ),
        8: (
            "button",
            "small_blind",
            "big_blind",
            "under_the_gun",
            "under_the_gun_plus_one",
            "middle_position",
            "hijack",
            "cutoff",
        ),
        9: (
            "button",
            "small_blind",
            "big_blind",
            "under_the_gun",
            "under_the_gun_plus_one",
            "middle_position",
            "lojack",
            "hijack",
            "cutoff",
        ),
        10: (
            "button",
            "small_blind",
            "big_blind",
            "under_the_gun",
            "under_the_gun_plus_one",
            "under_the_gun_plus_two",
            "middle_position",
            "lojack",
            "hijack",
            "cutoff",
        ),
    }
    return by_count[player_count]
