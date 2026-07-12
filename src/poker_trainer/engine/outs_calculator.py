"""Unique apparent outs calculation."""

from dataclasses import dataclass

from poker_trainer.engine.draw_detector import Draw, DrawType, detect_draws
from poker_trainer.models.card import Card
from poker_trainer.models.game_state import GameState


@dataclass(frozen=True, slots=True)
class OutsResult:
    """Grouped apparent outs with a de-duplicated card collection."""

    draws: tuple[Draw, ...]
    outs_by_draw: dict[DrawType, tuple[Card, ...]]
    unique_outs: tuple[Card, ...]
    clean_outs: tuple[Card, ...]
    limitation: str


def calculate_outs(game_state: GameState) -> OutsResult:
    """Calculate apparent outs without claiming range-adjusted cleanliness."""
    draws = detect_draws(game_state)
    outs_by_draw = {draw.draw_type: draw.outs for draw in draws if draw.outs}
    unique = tuple(
        sorted({card for draw in draws for card in draw.outs}, key=lambda card: card.code)
    )
    return OutsResult(
        draws=draws,
        outs_by_draw=outs_by_draw,
        unique_outs=unique,
        clean_outs=(),
        limitation=(
            "These are apparent unique outs. Clean and dirty outs require opponent-range analysis, "
            "which is intentionally outside this stage."
        ),
    )
