"""Pot odds and simplified expected value."""

from poker_trainer.models.recommendation import PotOddsResult
from poker_trainer.utils.exceptions import InvalidBetError

_LIMITATIONS = (
    "Simplified EV excludes future betting, rake, implied odds, reverse implied odds, "
    "range uncertainty, and opponent adaptation.",
)


def calculate_pot_odds(
    current_pot: float,
    amount_to_call: float,
    estimated_equity: float | None = None,
) -> PotOddsResult:
    """Calculate pot odds using the documented Peaceful Poker pot definition."""
    if current_pot < 0 or amount_to_call < 0:
        raise InvalidBetError("Pot and call amounts cannot be negative.")
    final_pot = current_pot + amount_to_call
    required = amount_to_call / final_pot if final_pot > 0 and amount_to_call > 0 else 0.0
    ratio = current_pot / amount_to_call if amount_to_call > 0 else None
    equity_difference = None if estimated_equity is None else estimated_equity - required
    call_ev = None
    if estimated_equity is not None:
        call_ev = estimated_equity * current_pot - (1.0 - estimated_equity) * amount_to_call
    return PotOddsResult(
        current_pot=current_pot,
        amount_to_call=amount_to_call,
        final_pot_after_call=final_pot,
        required_equity=required,
        pot_odds_ratio=ratio,
        estimated_equity=estimated_equity,
        equity_difference=equity_difference,
        simplified_call_ev=call_ev,
        limitations=_LIMITATIONS,
    )
