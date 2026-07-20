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
        "## Raw Showdown Analysis",
        "",
        "Assumption: every currently included opponent reaches showdown.",
        f"Pot-share equity: {result.equity.total_equity:.2%}",
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
    if result.action_aware is not None:
        lines.extend(
            [
                "",
                "## Action-Aware Analysis",
                "",
                "These EV estimates depend on entered opponent profiles and are not exact "
                "predictions.",
                f"Recommended action: {result.action_aware.recommended_action}",
                f"Second-best action: {result.action_aware.second_best_action or 'None'}",
                "EV gap: "
                + (
                    f"{result.action_aware.ev_difference:.2f} chips"
                    if result.action_aware.ev_difference is not None
                    else "Unavailable"
                ),
                "",
                "| Action | Pot % | Invest | Fold | Call | Raise | Called equity | "
                "Fold EV | Call EV | Raise EV | Net EV | 95% CI |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        lines.extend(_action_markdown_row(item) for item in result.action_aware.action_results)
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
    if result.action_aware is not None:
        payload["action_aware"] = {
            "recommended_action": result.action_aware.recommended_action,
            "second_best_action": result.action_aware.second_best_action,
            "ev_difference": result.action_aware.ev_difference,
            "result_is_close": result.action_aware.result_is_close,
            "all_in_recommended": result.action_aware.all_in_recommended,
            "uncertainty_note": result.action_aware.uncertainty_note,
            "simulations_per_action": result.action_aware.simulations_per_action,
            "assumptions": result.action_aware.assumptions,
            "actions": [
                {
                    "action": item.candidate.label,
                    "net_ev": item.estimated_net_ev,
                    "standard_error": item.standard_error,
                    "confidence_interval": [
                        item.confidence_interval_low,
                        item.confidence_interval_high,
                    ],
                    "all_fold": item.immediate_fold_probability,
                    "call": item.call_probability,
                    "continue": item.continue_probability,
                    "exactly_one_continues": item.exactly_one_continues_probability,
                    "multiple_continue": item.multiple_continue_probability,
                    "faces_raise": item.facing_raise_probability,
                    "showdown": item.showdown_probability,
                    "conditional_showdown_equity": item.conditional_showdown_equity,
                    "conditional_call_equity": item.conditional_call_equity,
                    "conditional_raise_equity": item.conditional_raise_equity,
                    "average_calling_range_strength": item.average_calling_range_strength,
                    "average_raising_range_strength": item.average_raising_range_strength,
                    "fold_ev_component": item.fold_ev_component,
                    "call_ev_component": item.call_ev_component,
                    "raise_ev_component": item.raise_ev_component,
                    "fold_branch_net_ev": item.fold_branch_net_ev,
                    "call_branch_net_ev": item.call_branch_net_ev,
                    "raise_branch_net_ev": item.raise_branch_net_ev,
                    "bet_percentage_of_pot": item.bet_percentage_of_pot,
                    "average_final_pot": item.average_final_pot,
                    "average_hero_investment": item.average_hero_investment,
                    "modelling_warnings": item.modelling_warnings,
                }
                for item in result.action_aware.action_results
            ],
        }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _action_markdown_row(item: Any) -> str:
    pot_percentage = (
        "N/A" if item.bet_percentage_of_pot is None else f"{item.bet_percentage_of_pot:.1f}%"
    )
    return (
        f"| {item.candidate.label} | {pot_percentage} | "
        f"{item.average_hero_investment:.2f} | {item.immediate_fold_probability:.2%} | "
        f"{item.call_probability:.2%} | {item.facing_raise_probability:.2%} | "
        f"{item.conditional_call_equity:.2%} | {item.fold_ev_component:.2f} | "
        f"{item.call_ev_component:.2f} | {item.raise_ev_component:.2f} | "
        f"{item.estimated_net_ev:.2f} | {item.confidence_interval_low:.2f} to "
        f"{item.confidence_interval_high:.2f} |"
    )
