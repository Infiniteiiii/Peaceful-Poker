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
    if game_state.amount_to_call == 0:
        actions = [PlayerAction.CHECK]
        if game_state.hero_stack > 0:
            actions.append(PlayerAction.BET)
            actions.append(PlayerAction.ALL_IN)
        return tuple(actions)

    if game_state.amount_to_call > game_state.hero_stack:
        raise InvalidBetError("Amount to call cannot exceed hero stack.")
    actions = [PlayerAction.FOLD, PlayerAction.CALL]
    if game_state.hero_stack > game_state.amount_to_call:
        if (
            minimum_raise is None
            or game_state.hero_stack >= game_state.amount_to_call + minimum_raise
        ):
            actions.append(PlayerAction.RAISE)
        actions.append(PlayerAction.ALL_IN)
    elif game_state.hero_stack == game_state.amount_to_call:
        actions.append(PlayerAction.ALL_IN)
    return tuple(dict.fromkeys(actions))
