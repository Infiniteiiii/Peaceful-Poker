"""Legal action detection for the current betting state."""

from enum import Enum

from poker_trainer.models.game_state import GameState
from poker_trainer.utils.exceptions import InvalidBetError


class PlayerAction(Enum):
    """Legal and recommended poker actions."""

    CHECK = "check"
    BET = "bet"
    FOLD = "fold"
    CALL = "call"
    RAISE = "raise"
    ALL_IN = "all_in"

    @property
    def display_name(self) -> str:
        """Return a user-facing action label."""
        return self.value.replace("_", " ").title()


def legal_actions(
    game_state: GameState, minimum_raise: float | None = None
) -> tuple[PlayerAction, ...]:
    """Return actions legal under the entered betting state."""
    if game_state.amount_to_call < 0 or game_state.hero_stack < 0:
        raise InvalidBetError("Betting values cannot be negative.")
    available = min(
        game_state.hero_stack,
        game_state.effective_stack or game_state.hero_stack,
    )
    if game_state.amount_to_call == 0:
        actions = [PlayerAction.CHECK]
        if available > 0:
            if available > game_state.big_blind:
                actions.append(PlayerAction.BET)
            actions.append(PlayerAction.ALL_IN)
        return tuple(actions)

    if game_state.amount_to_call > game_state.hero_stack:
        raise InvalidBetError("Amount to call cannot exceed hero stack.")
    if available <= game_state.amount_to_call:
        return (PlayerAction.FOLD, PlayerAction.ALL_IN)
    actions = [PlayerAction.FOLD, PlayerAction.CALL]
    if available > game_state.amount_to_call:
        required_raise = game_state.big_blind if minimum_raise is None else minimum_raise
        if available > game_state.amount_to_call + required_raise:
            actions.append(PlayerAction.RAISE)
        actions.append(PlayerAction.ALL_IN)
    return tuple(dict.fromkeys(actions))
