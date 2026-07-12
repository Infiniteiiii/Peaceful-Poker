"""Analysis export helpers."""

import json
from pathlib import Path
from typing import Any

from poker_trainer.services.analysis_service import AnalysisResult


def export_analysis_markdown(result: AnalysisResult, path: Path) -> Path:
    """Export a readable Markdown analysis report."""
    win_tie_loss = (
        f"Win/Tie/Loss: {result.equity.win_percentage:.2%} / "
        f"{result.equity.tie_percentage:.2%} / {result.equity.loss_percentage:.2%}"
    )
    lines = [
        "# Peaceful Poker Analysis",
        "",
        f"Street: {result.game_state.street.display_name}",
        f"Current hand: {result.current_hand.description}",
        f"Equity: {result.equity.total_equity:.2%}",
        win_tie_loss,
        f"Required equity: {result.pot_odds.required_equity:.2%}",
        f"Recommendation: {result.recommendation.primary_action}",
        "",
        "## Assumptions",
        *[f"- {assumption}" for assumption in result.recommendation.assumptions],
        "",
        "## Warnings",
        *[f"- {warning}" for warning in (*result.equity.warnings, result.outs.limitation)],
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def export_analysis_json(result: AnalysisResult, path: Path) -> Path:
    """Export a compact JSON analysis report."""
    payload: dict[str, Any] = {
        "street": result.game_state.street.value,
        "current_hand": result.current_hand.description,
        "equity": result.equity.total_equity,
        "win": result.equity.win_percentage,
        "tie": result.equity.tie_percentage,
        "loss": result.equity.loss_percentage,
        "required_equity": result.pot_odds.required_equity,
        "recommendation": result.recommendation.primary_action,
        "assumptions": result.recommendation.assumptions,
        "warnings": (*result.equity.warnings, result.outs.limitation),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
