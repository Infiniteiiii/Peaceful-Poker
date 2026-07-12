"""High-level analysis orchestration for Peaceful Poker."""

from dataclasses import dataclass

from poker_trainer.engine.board_analyzer import BoardAnalysis, analyze_board
from poker_trainer.engine.current_hand import CurrentHandAnalysis, analyze_current_hand
from poker_trainer.engine.draw_detector import Draw, detect_draws
from poker_trainer.engine.equity_calculator import (
    CancelCallback,
    ProgressCallback,
    calculate_equity,
)
from poker_trainer.engine.outs_calculator import OutsResult, calculate_outs
from poker_trainer.engine.probability_calculator import (
    FinalHandProbabilityResult,
    calculate_final_hand_probabilities,
)
from poker_trainer.models.equity import EquityResult
from poker_trainer.models.game_state import GameState
from poker_trainer.models.recommendation import PotOddsResult, Recommendation
from poker_trainer.strategy.action_recommender import recommend_action
from poker_trainer.strategy.pot_odds import calculate_pot_odds


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """Complete analyzer result used by services and UI."""

    game_state: GameState
    current_hand: CurrentHandAnalysis
    board_analysis: BoardAnalysis
    draws: tuple[Draw, ...]
    outs: OutsResult
    final_hand_probabilities: FinalHandProbabilityResult
    equity: EquityResult
    pot_odds: PotOddsResult
    recommendation: Recommendation


def analyze_game_state(
    game_state: GameState,
    opponent_range: str = "random",
    simulation_count: int | None = None,
    seed: int | None = None,
    progress_callback: ProgressCallback | None = None,
    cancel_callback: CancelCallback | None = None,
) -> AnalysisResult:
    """Run all currently implemented analysis systems for a game state."""
    current = analyze_current_hand(game_state)
    board = analyze_board(tuple(game_state.community_cards))
    draws = detect_draws(game_state)
    outs = calculate_outs(game_state)
    probabilities = calculate_final_hand_probabilities(game_state)
    equity = calculate_equity(
        game_state,
        simulation_count=simulation_count,
        seed=seed,
        opponent_range=opponent_range,
        progress_callback=progress_callback,
        cancel_callback=cancel_callback,
    )
    pot_odds = calculate_pot_odds(
        game_state.pot_size, game_state.amount_to_call, equity.total_equity
    )
    recommendation = recommend_action(game_state, equity, outs)
    return AnalysisResult(
        game_state=game_state,
        current_hand=current,
        board_analysis=board,
        draws=draws,
        outs=outs,
        final_hand_probabilities=probabilities,
        equity=equity,
        pot_odds=pot_odds,
        recommendation=recommendation,
    )
