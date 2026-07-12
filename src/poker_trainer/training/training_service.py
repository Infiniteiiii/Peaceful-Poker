"""Educational training-mode scenario generation."""

from dataclasses import dataclass, replace
from enum import Enum
from random import Random

from poker_trainer.models.action_aware import ActionAwareSettings, OpponentProfile
from poker_trainer.models.card import Card
from poker_trainer.models.game_state import GameState, Position
from poker_trainer.services.analysis_service import AnalysisResult, analyze_game_state


class TrainingDifficulty(Enum):
    """Training scenario difficulty levels."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class TrainingSituation(Enum):
    """Action-order situations emphasized by training mode."""

    LAST_TO_ACT = "hero_last_to_act"
    ONE_BEHIND = "one_player_behind"
    SEVERAL_BEHIND = "several_players_behind"
    TIGHT_BEHIND = "tight_players_behind"
    LOOSE_AGGRESSIVE_BEHIND = "loose_aggressive_players_behind"
    SHORT_STACK_BEHIND = "short_stack_players_behind"
    PRIOR_CALLERS = "players_called_before_hero"


@dataclass(frozen=True, slots=True)
class TrainingScenario:
    """A generated training hand with hidden recommendation until revealed."""

    difficulty: TrainingDifficulty
    situation: TrainingSituation
    game_state: GameState
    legal_action_labels: tuple[str, ...]
    analysis: AnalysisResult
    action_order_explanation: str


def generate_scenario(
    difficulty: TrainingDifficulty = TrainingDifficulty.BEGINNER,
    seed: int | None = None,
    situation: TrainingSituation | None = None,
) -> TrainingScenario:
    """Generate a deterministic valid training scenario from a small curated set."""
    selected = situation or _choose_situation(difficulty, Random(seed))
    state = generate_training_state(difficulty, seed, selected)
    analysis = analyze_game_state(
        state,
        simulation_count=1_000,
        seed=seed,
        include_action_aware=True,
        action_aware_settings=ActionAwareSettings(simulations_per_action=250),
    )
    behind = state.table_state.players_after_hero() if state.table_state is not None else ()
    return TrainingScenario(
        difficulty=difficulty,
        situation=selected,
        game_state=state,
        legal_action_labels=analysis.recommendation.legal_alternatives,
        analysis=analysis,
        action_order_explanation=(
            f"{len(behind)} opponent(s) remain to act behind hero. Their profiles can change "
            "fold, call, raise, and action-EV estimates."
        ),
    )


def generate_training_state(
    difficulty: TrainingDifficulty = TrainingDifficulty.BEGINNER,
    seed: int | None = None,
    situation: TrainingSituation | None = None,
) -> GameState:
    """Generate a valid scenario state without running a potentially slow analysis."""
    rng = Random(seed)
    selected = situation or _choose_situation(difficulty, rng)
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
    position = {
        TrainingSituation.LAST_TO_ACT: Position.BUTTON,
        TrainingSituation.ONE_BEHIND: Position.CUTOFF,
        TrainingSituation.SEVERAL_BEHIND: Position.SMALL_BLIND,
        TrainingSituation.TIGHT_BEHIND: Position.SMALL_BLIND,
        TrainingSituation.LOOSE_AGGRESSIVE_BEHIND: Position.SMALL_BLIND,
        TrainingSituation.SHORT_STACK_BEHIND: Position.SMALL_BLIND,
        TrainingSituation.PRIOR_CALLERS: Position.BUTTON,
    }[selected]
    state = GameState(
        active_players=players,
        hero_cards=_cards(hero),
        community_cards=_cards(board),
        hero_position=position,
        pot_size=pot,
        amount_to_call=call,
        hero_stack=stack,
        effective_stack=effective,
        small_blind=5.0,
        big_blind=10.0,
        requested_simulation_count=5_000,
    )
    if state.table_state is None:
        return state
    table = state.table_state
    clockwise = tuple(
        player.seat for player in table.clockwise_after(table.hero_seat) if not player.is_hero
    )
    behind_count = {
        TrainingSituation.LAST_TO_ACT: 0,
        TrainingSituation.ONE_BEHIND: 1,
        TrainingSituation.SEVERAL_BEHIND: min(3, len(clockwise)),
        TrainingSituation.TIGHT_BEHIND: min(3, len(clockwise)),
        TrainingSituation.LOOSE_AGGRESSIVE_BEHIND: min(3, len(clockwise)),
        TrainingSituation.SHORT_STACK_BEHIND: min(2, len(clockwise)),
        TrainingSituation.PRIOR_CALLERS: 0,
    }[selected]
    behind = set(clockwise[:behind_count])
    configured_players = []
    for player in table.players:
        if player.is_hero:
            configured_players.append(player)
            continue
        profile = OpponentProfile.UNKNOWN_BALANCED
        if selected is TrainingSituation.TIGHT_BEHIND and player.seat in behind:
            profile = OpponentProfile.TIGHT_PASSIVE
        elif selected is TrainingSituation.LOOSE_AGGRESSIVE_BEHIND and player.seat in behind:
            profile = OpponentProfile.LOOSE_AGGRESSIVE
        stack_value = (
            min(player.stack, 60.0)
            if selected is TrainingSituation.SHORT_STACK_BEHIND and player.seat in behind
            else player.stack
        )
        called = selected is TrainingSituation.PRIOR_CALLERS and player.acted_this_round
        contribution = min(20.0, stack_value) if called else player.round_contribution
        configured_players.append(
            replace(
                player,
                stack=stack_value,
                profile=profile,
                previous_actions=("Called",) if called else player.previous_actions,
                acted_this_round=player.seat not in behind,
                round_contribution=contribution,
                total_contribution=max(player.total_contribution, contribution),
            )
        )
    return replace(state, table_state=replace(table, players=tuple(configured_players)))


def _choose_situation(difficulty: TrainingDifficulty, rng: Random) -> TrainingSituation:
    choices = {
        TrainingDifficulty.BEGINNER: (
            TrainingSituation.LAST_TO_ACT,
            TrainingSituation.ONE_BEHIND,
        ),
        TrainingDifficulty.INTERMEDIATE: (
            TrainingSituation.SEVERAL_BEHIND,
            TrainingSituation.TIGHT_BEHIND,
            TrainingSituation.PRIOR_CALLERS,
        ),
        TrainingDifficulty.ADVANCED: (
            TrainingSituation.LOOSE_AGGRESSIVE_BEHIND,
            TrainingSituation.SHORT_STACK_BEHIND,
        ),
    }
    return rng.choice(choices[difficulty])


def _cards(codes: str) -> tuple[Card, ...]:
    return tuple(Card.from_code(code) for code in codes.split())
