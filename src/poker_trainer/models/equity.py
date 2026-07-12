"""Equity calculation result models."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EquityResult:
    """Showdown equity result against modeled opponent holdings."""

    wins: int
    losses: int
    ties: int
    pot_share_total: float
    win_percentage: float
    loss_percentage: float
    tie_percentage: float
    total_equity: float
    iterations: int
    calculation_method: str
    random_seed: int | None
    execution_time: float
    warnings: tuple[str, ...]
    assumptions: tuple[str, ...]


class SimulationPreset:
    """Named simulation counts used by the analyzer and UI."""

    QUICK = 5_000
    STANDARD = 25_000
    ACCURATE = 100_000
    VERY_ACCURATE = 500_000
