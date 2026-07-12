"""Recommendation and betting result models."""

from dataclasses import dataclass
from enum import Enum


class ConfidenceLevel(Enum):
    """Rule-based confidence labels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class PotOddsResult:
    """Pot odds and simplified call EV."""

    current_pot: float
    amount_to_call: float
    final_pot_after_call: float
    required_equity: float
    pot_odds_ratio: float | None
    estimated_equity: float | None
    equity_difference: float | None
    simplified_call_ev: float | None
    limitations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Recommendation:
    """Educational rule-based action recommendation."""

    primary_action: str
    confidence: ConfidenceLevel
    suggested_size: float | None
    legal_alternatives: tuple[str, ...]
    reasons: tuple[str, ...]
    risks: tuple[str, ...]
    assumptions: tuple[str, ...]
    explanation: str
