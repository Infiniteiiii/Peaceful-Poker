"""Exact and Monte Carlo showdown equity calculations."""

from collections.abc import Callable, Sequence
from itertools import combinations
from random import Random
from time import perf_counter

from poker_trainer.engine.hand_evaluator import HandScore, evaluate_hand_score
from poker_trainer.engine.range_parser import CardCombo, available_combinations, filter_combinations
from poker_trainer.models.card import Card
from poker_trainer.models.deck import Deck
from poker_trainer.models.equity import EquityResult, SimulationPreset
from poker_trainer.models.game_state import GameState, Street
from poker_trainer.utils.exceptions import InvalidGameStateError, SimulationCancelledError

ProgressCallback = Callable[[int, int], None]
CancelCallback = Callable[[], bool]

_EXACT_OUTCOME_THRESHOLD = 150_000


def calculate_equity(
    game_state: GameState,
    simulation_count: int | None = None,
    seed: int | None = None,
    opponent_range: str = "random",
    known_opponent_hands: Sequence[Sequence[Card]] = (),
    progress_callback: ProgressCallback | None = None,
    cancel_callback: CancelCallback | None = None,
    exact_threshold: int = _EXACT_OUTCOME_THRESHOLD,
) -> EquityResult:
    """Calculate hero showdown equity against valid opponent holdings."""
    count = simulation_count or game_state.requested_simulation_count or SimulationPreset.STANDARD
    if count <= 0:
        raise InvalidGameStateError("Simulation count must be positive.")
    if exact_threshold < 0:
        raise InvalidGameStateError("Exact calculation threshold cannot be negative.")
    known_hands = tuple(tuple(hand) for hand in known_opponent_hands)
    _validate_known_opponents(game_state, known_hands)
    start = perf_counter()
    warnings: list[str] = []
    assumptions = [f"Opponent range assumption: {opponent_range}."]
    exact_outcomes = _estimate_exact_outcomes(game_state, opponent_range, known_hands)
    if exact_outcomes is not None and exact_outcomes <= exact_threshold:
        result = _calculate_exact(
            game_state,
            opponent_range,
            known_hands,
            start,
            progress_callback,
            cancel_callback,
        )
    else:
        if exact_outcomes is not None:
            warnings.append(
                "Exact state space "
                f"({exact_outcomes} outcomes) exceeded threshold {exact_threshold}."
            )
        result = _calculate_monte_carlo(
            game_state,
            count,
            seed,
            opponent_range,
            known_hands,
            start,
            progress_callback,
            cancel_callback,
        )
    if warnings:
        result = _with_extra_warnings(result, tuple(warnings))
    if assumptions:
        result = _with_extra_assumptions(result, tuple(assumptions))
    return result


def _calculate_exact(
    game_state: GameState,
    opponent_range: str,
    known_opponent_hands: tuple[tuple[Card, ...], ...],
    start: float,
    progress_callback: ProgressCallback | None,
    cancel_callback: CancelCallback | None,
) -> EquityResult:
    remaining = _remaining_deck(game_state, known_opponent_hands)
    board_runouts = _board_runouts(game_state, remaining)
    total_steps = max(1, len(board_runouts))
    wins = losses = ties = 0
    pot_share_total = 0.0
    iterations = 0
    for step, runout in enumerate(board_runouts, start=1):
        _raise_if_cancelled(cancel_callback)
        board = (*game_state.community_cards, *runout)
        hero_score = evaluate_hand_score((*game_state.hero_cards, *board))
        used_for_board = set(runout)
        available_after_board = tuple(card for card in remaining if card not in used_for_board)
        unknown_count = game_state.active_players - 1 - len(known_opponent_hands)
        for opponent_hands in _opponent_hand_assignments(
            available_after_board,
            unknown_count,
            opponent_range,
        ):
            all_opponents = (*known_opponent_hands, *opponent_hands)
            share = _hero_pot_share(hero_score, board, all_opponents)
            wins, losses, ties = _record_share(share, wins, losses, ties)
            pot_share_total += share
            iterations += 1
        if progress_callback is not None:
            progress_callback(step, total_steps)
    return _build_result(
        wins=wins,
        losses=losses,
        ties=ties,
        pot_share_total=pot_share_total,
        iterations=iterations,
        method="exact_enumeration",
        seed=None,
        start=start,
        warnings=(),
    )


def _calculate_monte_carlo(
    game_state: GameState,
    simulation_count: int,
    seed: int | None,
    opponent_range: str,
    known_opponent_hands: tuple[tuple[Card, ...], ...],
    start: float,
    progress_callback: ProgressCallback | None,
    cancel_callback: CancelCallback | None,
) -> EquityResult:
    rng = Random(seed)
    wins = losses = ties = 0
    pot_share_total = 0.0
    for iteration in range(1, simulation_count + 1):
        _raise_if_cancelled(cancel_callback)
        remaining = list(_remaining_deck(game_state, known_opponent_hands))
        opponent_hands = list(known_opponent_hands)
        unknown_count = game_state.active_players - 1 - len(known_opponent_hands)
        if _is_random_range(opponent_range):
            rng.shuffle(remaining)
            opponent_cards = remaining[: unknown_count * 2]
            opponent_hands.extend(
                tuple(opponent_cards[index : index + 2])
                for index in range(0, len(opponent_cards), 2)
            )
            del remaining[: unknown_count * 2]
        else:
            for _ in range(unknown_count):
                combo = _pick_combo(remaining, opponent_range, rng)
                opponent_hands.append(combo)
                remaining.remove(combo[0])
                remaining.remove(combo[1])
            rng.shuffle(remaining)
        board = (*game_state.community_cards, *remaining[: 5 - len(game_state.community_cards)])
        hero_score = evaluate_hand_score((*game_state.hero_cards, *board))
        share = _hero_pot_share(hero_score, board, tuple(opponent_hands))
        wins, losses, ties = _record_share(share, wins, losses, ties)
        pot_share_total += share
        if progress_callback is not None and (
            iteration == simulation_count or iteration % 100 == 0
        ):
            progress_callback(iteration, simulation_count)
    return _build_result(
        wins=wins,
        losses=losses,
        ties=ties,
        pot_share_total=pot_share_total,
        iterations=simulation_count,
        method="monte_carlo",
        seed=seed,
        start=start,
        warnings=(),
    )


def _remaining_deck(
    game_state: GameState,
    known_opponent_hands: tuple[tuple[Card, ...], ...],
) -> tuple[Card, ...]:
    deck = Deck.standard()
    known = [*game_state.known_cards]
    for hand in known_opponent_hands:
        known.extend(hand)
    deck.remove_many(known)
    return deck.remaining()


def _board_runouts(
    game_state: GameState, remaining: tuple[Card, ...]
) -> tuple[tuple[Card, ...], ...]:
    needed = 5 - len(game_state.community_cards)
    if needed == 0:
        return ((),)
    return tuple(combinations(remaining, needed))


def _opponent_hand_assignments(
    available: tuple[Card, ...],
    opponent_count: int,
    opponent_range: str,
) -> tuple[tuple[tuple[Card, ...], ...], ...]:
    if opponent_count <= 0:
        return ((),)
    assignments: list[tuple[tuple[Card, ...], ...]] = []

    def build(
        deck_cards: tuple[Card, ...], hands_left: int, acc: tuple[tuple[Card, ...], ...]
    ) -> None:
        if hands_left == 0:
            assignments.append(acc)
            return
        combos = filter_combinations(available_combinations(deck_cards), opponent_range)
        for combo in combos:
            remaining = tuple(card for card in deck_cards if card not in combo)
            build(remaining, hands_left - 1, (*acc, combo))

    build(available, opponent_count, ())
    return tuple(assignments)


def _pick_combo(available: list[Card], opponent_range: str, rng: Random) -> CardCombo:
    combos = filter_combinations(available_combinations(tuple(available)), opponent_range)
    if not combos:
        combos = available_combinations(tuple(available))
    return combos[rng.randrange(len(combos))]


def _hero_pot_share(
    hero_score: HandScore,
    board: tuple[Card, ...],
    opponent_hands: tuple[tuple[Card, ...], ...],
) -> float:
    opponent_scores = tuple(evaluate_hand_score((*hand, *board)) for hand in opponent_hands)
    all_scores = (hero_score, *opponent_scores)
    best = max(all_scores)
    winners = sum(1 for score in all_scores if score == best)
    return 1.0 / winners if hero_score == best else 0.0


def _record_share(share: float, wins: int, losses: int, ties: int) -> tuple[int, int, int]:
    if share == 1.0:
        return wins + 1, losses, ties
    if share > 0.0:
        return wins, losses, ties + 1
    return wins, losses + 1, ties


def _build_result(
    *,
    wins: int,
    losses: int,
    ties: int,
    pot_share_total: float,
    iterations: int,
    method: str,
    seed: int | None,
    start: float,
    warnings: tuple[str, ...],
) -> EquityResult:
    denominator = iterations or 1
    return EquityResult(
        wins=wins,
        losses=losses,
        ties=ties,
        pot_share_total=pot_share_total,
        win_percentage=wins / denominator,
        loss_percentage=losses / denominator,
        tie_percentage=ties / denominator,
        total_equity=pot_share_total / denominator,
        iterations=iterations,
        calculation_method=method,
        random_seed=seed,
        execution_time=perf_counter() - start,
        warnings=warnings,
        assumptions=(),
    )


def _estimate_exact_outcomes(
    game_state: GameState,
    opponent_range: str,
    known_opponent_hands: tuple[tuple[Card, ...], ...],
) -> int | None:
    unknown_count = game_state.active_players - 1 - len(known_opponent_hands)
    if unknown_count < 0:
        return None
    if game_state.street is Street.PREFLOP and unknown_count > 0:
        return None
    if unknown_count > 1:
        return None
    remaining = _remaining_deck(game_state, known_opponent_hands)
    runout_count = len(_board_runouts(game_state, remaining))
    if unknown_count == 0:
        return runout_count
    total = 0
    for runout in _board_runouts(game_state, remaining):
        available_after_board = tuple(card for card in remaining if card not in runout)
        total += len(
            filter_combinations(available_combinations(available_after_board), opponent_range)
        )
    return total


def _raise_if_cancelled(cancel_callback: CancelCallback | None) -> None:
    if cancel_callback is not None and cancel_callback():
        raise SimulationCancelledError("Equity calculation was cancelled.")


def _validate_known_opponents(
    game_state: GameState, known_opponent_hands: tuple[tuple[Card, ...], ...]
) -> None:
    if len(known_opponent_hands) > game_state.active_players - 1:
        raise InvalidGameStateError("Known opponent hands exceed the active opponent count.")
    if any(len(hand) != 2 for hand in known_opponent_hands):
        raise InvalidGameStateError("Every known opponent hand must contain exactly two cards.")
    known_cards = [*game_state.known_cards]
    for hand in known_opponent_hands:
        known_cards.extend(hand)
    if len(set(known_cards)) != len(known_cards):
        raise InvalidGameStateError("Known hero, board, and opponent cards cannot overlap.")


def _is_random_range(opponent_range: str) -> bool:
    return opponent_range.strip().lower() in {"", "random", "any two"}


def _with_extra_warnings(result: EquityResult, warnings: tuple[str, ...]) -> EquityResult:
    return EquityResult(
        wins=result.wins,
        losses=result.losses,
        ties=result.ties,
        pot_share_total=result.pot_share_total,
        win_percentage=result.win_percentage,
        loss_percentage=result.loss_percentage,
        tie_percentage=result.tie_percentage,
        total_equity=result.total_equity,
        iterations=result.iterations,
        calculation_method=result.calculation_method,
        random_seed=result.random_seed,
        execution_time=result.execution_time,
        warnings=(*result.warnings, *warnings),
        assumptions=result.assumptions,
    )


def _with_extra_assumptions(result: EquityResult, assumptions: tuple[str, ...]) -> EquityResult:
    return EquityResult(
        wins=result.wins,
        losses=result.losses,
        ties=result.ties,
        pot_share_total=result.pot_share_total,
        win_percentage=result.win_percentage,
        loss_percentage=result.loss_percentage,
        tie_percentage=result.tie_percentage,
        total_equity=result.total_equity,
        iterations=result.iterations,
        calculation_method=result.calculation_method,
        random_seed=result.random_seed,
        execution_time=result.execution_time,
        warnings=result.warnings,
        assumptions=(*result.assumptions, *assumptions),
    )
