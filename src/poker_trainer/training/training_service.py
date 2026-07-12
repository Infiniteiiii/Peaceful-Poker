"""Educational training-mode scenario generation."""

from dataclasses import dataclass
from enum import Enum
from random import Random

from poker_trainer.models.card import Card
from poker_trainer.models.game_state import GameState, Position
from poker_trainer.services.analysis_service import AnalysisResult, analyze_game_state


class TrainingDifficulty(Enum):
    """Training scenario difficulty levels."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


@dataclass(frozen=True, slots=True)
class TrainingScenario:
    """A generated training hand with hidden recommendation until revealed."""

    difficulty: TrainingDifficulty
    game_state: GameState
    legal_action_labels: tuple[str, ...]
    analysis: AnalysisResult


def generate_scenario(
    difficulty: TrainingDifficulty = TrainingDifficulty.BEGINNER,
    seed: int | None = None,
) -> TrainingScenario:
    """Generate a deterministic valid training scenario from a small curated set."""
    state = generate_training_state(difficulty, seed)
    analysis = analyze_game_state(state, simulation_count=1_000, seed=seed)
    return TrainingScenario(
        difficulty=difficulty,
        game_state=state,
        legal_action_labels=analysis.recommendation.legal_alternatives,
        analysis=analysis,
    )


def generate_training_state(
    difficulty: TrainingDifficulty = TrainingDifficulty.BEGINNER,
    seed: int | None = None,
) -> GameState:
    """Generate a valid scenario state without running a potentially slow analysis."""
    rng = Random(seed)
    scenarios = {
        TrainingDifficulty.BEGINNER: [
            ("AS KS", "QS 10D 4S", 6, 140.0, 40.0, 900.0, 620.0),
            ("AH AD", "7C 2D 9S", 2, 100.0, 0.0, 500.0, 500.0),
        ],
        TrainingDifficulty.INTERMEDIATE: [
            ("9S 8S", "7S 6D 2C", 3, 120.0, 30.0, 700.0, 650.0),
            ("QC JD", "10S 9H 2D", 4, 180.0, 60.0, 800.0, 700.0),
        ],
        TrainingDifficulty.ADVANCED: [
            ("AS 5S", "KS 7S 7D", 5, 220.0, 90.0, 850.0, 620.0),
            ("6C 6D", "AS KD 9H", 6, 160.0, 55.0, 600.0, 600.0),
        ],
    }
    hero, board, players, pot, call, stack, effective = rng.choice(scenarios[difficulty])
    state = GameState(
        active_players=players,
        hero_cards=_cards(hero),
        community_cards=_cards(board),
        hero_position=Position.BUTTON,
        pot_size=pot,
        amount_to_call=call,
        hero_stack=stack,
        effective_stack=effective,
        small_blind=5.0,
        big_blind=10.0,
        requested_simulation_count=5_000,
    )
    return state


def _cards(codes: str) -> tuple[Card, ...]:
    return tuple(Card.from_code(code) for code in codes.split())
