"""Bounded action-aware Monte Carlo decision simulation."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from math import sqrt
from random import Random
from time import perf_counter

from poker_trainer.engine.board_analyzer import analyze_board
from poker_trainer.engine.candidate_actions import generate_candidate_actions
from poker_trainer.engine.hand_evaluator import HandScore, evaluate_hand_score
from poker_trainer.engine.opponent_policy import (
    PolicyContext,
    classify_opponent_hand,
    legal_opponent_actions,
    load_opponent_profiles,
    opponent_action_distribution,
)
from poker_trainer.engine.range_parser import (
    available_combinations,
    combination_matches_range,
    filter_combinations,
)
from poker_trainer.models.action_aware import (
    ActionAwareResult,
    ActionAwareSettings,
    ActionDistribution,
    CandidateActionResult,
    HeroActionKind,
    HeroCandidateAction,
    OpponentAction,
    PolicySimulationMode,
    RelativeHandStrength,
    TablePlayer,
)
from poker_trainer.models.card import Card
from poker_trainer.models.deck import Deck
from poker_trainer.models.game_state import GameState
from poker_trainer.utils.exceptions import (
    InvalidGameStateError,
    SimulationCancelledError,
    UnsupportedRangeError,
)

ProgressCallback = Callable[[int, int], None]
CancelCallback = Callable[[], bool]
OpponentPolicyCallback = Callable[
    [TablePlayer, tuple[Card, Card], tuple[Card, ...], PolicyContext],
    ActionDistribution,
]


@dataclass(slots=True)
class _SimPlayer:
    player: TablePlayer
    hole_cards: tuple[Card, Card]
    stack: float
    contribution: float
    folded: bool
    all_in: bool
    additional_investment: float = 0.0

    @property
    def can_act(self) -> bool:
        return not self.folded and not self.all_in and self.stack > 0

    @property
    def reaches_showdown(self) -> bool:
        return not self.folded


@dataclass(frozen=True, slots=True)
class _IterationResult:
    net_result: float
    immediate_fold: bool
    opponents_continuing: int
    faced_raise: bool
    reached_showdown: bool
    showdown_share: float
    final_pot: float
    hero_investment: float


@dataclass(slots=True)
class _Accumulator:
    count: int = 0
    mean: float = 0.0
    m2: float = 0.0
    immediate_folds: int = 0
    exactly_one: int = 0
    multiple: int = 0
    faced_raises: int = 0
    showdowns: int = 0
    showdown_share_total: float = 0.0
    final_pot_total: float = 0.0
    hero_investment_total: float = 0.0

    def record(self, result: _IterationResult) -> None:
        self.count += 1
        delta = result.net_result - self.mean
        self.mean += delta / self.count
        self.m2 += delta * (result.net_result - self.mean)
        self.immediate_folds += int(result.immediate_fold)
        self.exactly_one += int(result.opponents_continuing == 1)
        self.multiple += int(result.opponents_continuing > 1)
        self.faced_raises += int(result.faced_raise)
        self.showdowns += int(result.reached_showdown)
        self.showdown_share_total += result.showdown_share
        self.final_pot_total += result.final_pot
        self.hero_investment_total += result.hero_investment


def action_aware_preset(name: str) -> ActionAwareSettings:
    """Return documented Quick, Standard, or Accurate policy settings."""
    normalized = name.strip().lower()
    if normalized == "quick":
        return ActionAwareSettings(
            mode=PolicySimulationMode.FAST,
            simulations_per_action=2_500,
            maximum_raises_per_street=1,
            maximum_action_depth=20,
        )
    if normalized == "standard":
        return ActionAwareSettings(
            mode=PolicySimulationMode.DETAILED,
            simulations_per_action=10_000,
            maximum_raises_per_street=2,
            maximum_action_depth=30,
        )
    if normalized == "accurate":
        return ActionAwareSettings(
            mode=PolicySimulationMode.DETAILED,
            simulations_per_action=30_000,
            maximum_raises_per_street=2,
            maximum_action_depth=40,
        )
    raise InvalidGameStateError("Action-aware preset must be Quick, Standard, or Accurate.")


def calculate_action_aware_ev(
    game_state: GameState,
    settings: ActionAwareSettings | None = None,
    seed: int | None = None,
    progress_callback: ProgressCallback | None = None,
    cancel_callback: CancelCallback | None = None,
    policy_callback: OpponentPolicyCallback | None = None,
) -> ActionAwareResult:
    """Estimate every legal candidate's future net chip EV under policy assumptions."""
    values = settings or action_aware_preset("quick")
    candidates = generate_candidate_actions(game_state)
    start = perf_counter()
    total_steps = len(candidates) * values.simulations_per_action
    results: list[CandidateActionResult] = []
    for candidate_index, candidate in enumerate(candidates):
        _raise_if_cancelled(cancel_callback)
        if candidate.kind is HeroActionKind.FOLD:
            result = _fold_result(candidate, values.simulations_per_action)
            results.append(result)
            if progress_callback is not None:
                progress_callback(
                    (candidate_index + 1) * values.simulations_per_action,
                    total_steps,
                )
            continue
        rng = Random(None if seed is None else seed + candidate_index * 1_000_003)
        accumulator = _Accumulator()
        for iteration in range(1, values.simulations_per_action + 1):
            _raise_if_cancelled(cancel_callback)
            accumulator.record(
                _simulate_iteration(game_state, candidate, values, rng, policy_callback)
            )
            completed = candidate_index * values.simulations_per_action + iteration
            if progress_callback is not None and (
                iteration % 100 == 0 or iteration == values.simulations_per_action
            ):
                progress_callback(completed, total_steps)
        results.append(_build_candidate_result(candidate, accumulator))
    recommendation, uncertainty = _recommend(tuple(results))
    return ActionAwareResult(
        action_results=tuple(results),
        recommended_action=recommendation,
        uncertainty_note=uncertainty,
        simulations_per_action=values.simulations_per_action,
        random_seed=seed,
        execution_time=perf_counter() - start,
        assumptions=(
            "Action-aware EV is a bounded Monte Carlo estimate, not exact opponent prediction.",
            f"Policy mode: {values.mode.value}; "
            f"maximum raises: {values.maximum_raises_per_street}.",
            "Future streets complete to showdown after the bounded current-street policy sequence.",
            "Previous contributions are sunk; EV tracks chips returned minus new hero investment.",
            "Opponent profiles and ranges are transparent behavioral assumptions.",
        ),
    )


def _simulate_iteration(
    game_state: GameState,
    candidate: HeroCandidateAction,
    settings: ActionAwareSettings,
    rng: Random,
    policy_callback: OpponentPolicyCallback | None,
) -> _IterationResult:
    table = game_state.table_state
    if table is None:
        raise InvalidGameStateError("Action-aware analysis requires table state.")
    opponents, remaining = _deal_opponents(game_state, rng)
    original_pot = game_state.pot_size
    pot = original_pot + candidate.additional_investment
    hero_investment = candidate.additional_investment
    hero_stack = max(0.0, table.hero.stack - candidate.additional_investment)
    hero_contribution = candidate.target_round_contribution
    hero_all_in = hero_stack <= 0
    highest = max(
        [hero_contribution, *(state.contribution for state in opponents.values())],
        default=hero_contribution,
    )
    prior_highest = max(
        [
            table.hero.round_contribution + game_state.amount_to_call,
            *(player.round_contribution for player in table.players if not player.is_hero),
        ]
    )
    aggression_reopens = (
        candidate.kind
        in {
            HeroActionKind.BET,
            HeroActionKind.RAISE,
            HeroActionKind.ALL_IN,
        }
        and hero_contribution > prior_highest
    )
    queue = list(table.response_order_after_hero(aggression_reopens=aggression_reopens))
    raises = int(candidate.kind is HeroActionKind.RAISE)
    faced_raise = False
    depth = 0
    board_analysis = analyze_board(tuple(game_state.community_cards))
    while queue and depth < settings.maximum_action_depth:
        depth += 1
        seat = queue.pop(0)
        state = opponents.get(seat)
        if state is None or not state.can_act:
            continue
        amount_to_call = max(0.0, highest - state.contribution)
        context = PolicyContext(
            pot_size=pot,
            amount_to_call=amount_to_call,
            minimum_raise=max(game_state.big_blind, highest - state.contribution, 0.0),
            board_analysis=board_analysis,
            opponents_remaining=sum(
                1 for other in opponents.values() if not other.folded and other.player.seat != seat
            ),
            position_fraction=_position_fraction(table.action_order(), seat),
            prior_aggression=_prior_aggression(state.player),
            raises_so_far=raises,
            maximum_raises=settings.maximum_raises_per_street,
        )
        policy_player = replace(
            state.player,
            stack=state.stack,
            round_contribution=state.contribution,
            total_contribution=max(state.player.total_contribution, state.contribution),
            folded=state.folded,
            all_in=state.all_in,
        )
        policy = policy_callback or opponent_action_distribution
        distribution = policy(
            policy_player,
            state.hole_cards,
            tuple(game_state.community_cards),
            context,
        )
        legal = set(legal_opponent_actions(policy_player, context))
        if not set(distribution.probabilities).issubset(legal):
            raise InvalidGameStateError("Opponent policy returned an illegal action.")
        action = _sample_action(distribution.probabilities, rng)
        old_highest = highest
        pot, highest = _apply_opponent_action(
            state,
            action,
            pot,
            highest,
            amount_to_call,
            context.minimum_raise,
        )
        if highest > old_highest:
            raises += 1
            faced_raise = aggression_reopens or candidate.kind in {
                HeroActionKind.CALL,
                HeroActionKind.BET,
                HeroActionKind.RAISE,
            }
            reopened = table.reopened_order_after_raise(seat)
            pending = set(queue)
            for reopened_seat in reopened:
                reopened_state = opponents.get(reopened_seat)
                if (
                    reopened_state is not None
                    and reopened_state.can_act
                    and reopened_state.contribution < highest
                    and reopened_seat not in pending
                ):
                    queue.append(reopened_seat)
                    pending.add(reopened_seat)

    if highest > hero_contribution and not hero_all_in:
        faced_raise = True
        additional_call = min(hero_stack, highest - hero_contribution)
        if _hero_continues_to_aggression(game_state, pot, additional_call, rng):
            hero_investment += additional_call
            hero_stack -= additional_call
            hero_contribution += additional_call
            pot += additional_call
            hero_all_in = hero_stack <= 0
        else:
            return _IterationResult(
                net_result=-hero_investment,
                immediate_fold=False,
                opponents_continuing=sum(
                    1 for state in opponents.values() if state.reaches_showdown
                ),
                faced_raise=faced_raise,
                reached_showdown=False,
                showdown_share=0.0,
                final_pot=pot,
                hero_investment=hero_investment,
            )

    continuing = tuple(state for state in opponents.values() if state.reaches_showdown)
    if not continuing:
        return _IterationResult(
            net_result=pot - hero_investment,
            immediate_fold=aggression_reopens,
            opponents_continuing=0,
            faced_raise=faced_raise,
            reached_showdown=False,
            showdown_share=0.0,
            final_pot=pot,
            hero_investment=hero_investment,
        )

    rng.shuffle(remaining)
    board_needed = 5 - len(game_state.community_cards)
    board = (*game_state.community_cards, *remaining[:board_needed])
    hero_score = evaluate_hand_score((*game_state.hero_cards, *board))
    opponent_scores = tuple(
        evaluate_hand_score((*state.hole_cards, *board)) for state in continuing
    )
    share = _pot_share(hero_score, opponent_scores)
    returned = _hero_showdown_return(
        original_pot,
        hero_investment,
        hero_score,
        opponents,
        opponent_scores,
    )
    return _IterationResult(
        net_result=returned - hero_investment,
        immediate_fold=False,
        opponents_continuing=len(continuing),
        faced_raise=faced_raise,
        reached_showdown=True,
        showdown_share=share,
        final_pot=pot,
        hero_investment=hero_investment,
    )


def _deal_opponents(game_state: GameState, rng: Random) -> tuple[dict[int, _SimPlayer], list[Card]]:
    table = game_state.table_state
    if table is None:
        raise InvalidGameStateError("Action-aware analysis requires table state.")
    deck = Deck.standard()
    deck.remove_many(game_state.known_cards)
    remaining = list(deck.remaining())
    states: dict[int, _SimPlayer] = {}
    for player in table.players:
        if player.is_hero or not player.dealt_in:
            continue
        profile = load_opponent_profiles()[player.profile]
        range_text = player.range_text
        if (
            range_text.strip().lower() in {"", "random", "profile"}
            and player.profile.value != "custom"
        ):
            range_text = (
                profile.preflop_range
                if game_state.street.value == "preflop"
                else profile.postflop_range
            )
        if range_text.strip().lower() in {"", "random", "any two"}:
            first_index = rng.randrange(len(remaining))
            first = remaining.pop(first_index)
            second_index = rng.randrange(len(remaining))
            second = remaining.pop(second_index)
            combo = (first, second)
        else:
            combo = _sample_filtered_combo(remaining, range_text, rng)
            remaining.remove(combo[0])
            remaining.remove(combo[1])
        states[player.seat] = _SimPlayer(
            player=player,
            hole_cards=combo,
            stack=player.stack,
            contribution=player.round_contribution,
            folded=player.folded,
            all_in=player.all_in,
        )
    return states, remaining


def _sample_filtered_combo(
    remaining: list[Card], range_text: str, rng: Random
) -> tuple[Card, Card]:
    for _ in range(80):
        first, second = rng.sample(remaining, 2)
        try:
            if combination_matches_range((first, second), range_text):
                return (first, second)
        except UnsupportedRangeError:
            break
    combos = available_combinations(tuple(remaining))
    try:
        filtered = filter_combinations(combos, range_text)
    except UnsupportedRangeError:
        filtered = combos
    if not filtered:
        filtered = combos
    return filtered[rng.randrange(len(filtered))]


def _apply_opponent_action(
    state: _SimPlayer,
    action: OpponentAction,
    pot: float,
    highest: float,
    amount_to_call: float,
    minimum_raise: float,
) -> tuple[float, float]:
    if action is OpponentAction.FOLD:
        state.folded = True
        return pot, highest
    if action is OpponentAction.CHECK:
        return pot, highest
    if action is OpponentAction.CALL:
        paid = min(state.stack, amount_to_call)
    elif action is OpponentAction.RAISE:
        paid = min(state.stack, amount_to_call + max(minimum_raise, amount_to_call))
    elif action is OpponentAction.BET_SMALL:
        paid = min(state.stack, max(1.0, pot * 0.33))
    elif action is OpponentAction.BET_MEDIUM:
        paid = min(state.stack, max(1.0, pot * 0.60))
    elif action is OpponentAction.BET_LARGE:
        paid = min(state.stack, max(1.0, pot * 0.90))
    else:
        paid = state.stack
    paid = max(0.0, min(paid, state.stack))
    state.stack -= paid
    state.contribution += paid
    state.additional_investment += paid
    state.all_in = state.stack <= 0
    return pot + paid, max(highest, state.contribution)


def _hero_continues_to_aggression(
    game_state: GameState, pot: float, amount_to_call: float, rng: Random
) -> bool:
    if amount_to_call <= 0:
        return True
    strength = classify_opponent_hand(
        (game_state.hero_cards[0], game_state.hero_cards[1]),
        tuple(game_state.community_cards),
    )
    strength_value = {
        RelativeHandStrength.VERY_WEAK: 0.08,
        RelativeHandStrength.WEAK_SHOWDOWN_VALUE: 0.25,
        RelativeHandStrength.DRAW: 0.50,
        RelativeHandStrength.MEDIUM_MADE_HAND: 0.64,
        RelativeHandStrength.STRONG_MADE_HAND: 0.84,
        RelativeHandStrength.VERY_STRONG: 0.98,
    }[strength]
    required = amount_to_call / max(pot + amount_to_call, 1.0)
    continue_probability = max(0.03, min(0.97, 0.20 + strength_value - required))
    return rng.random() < continue_probability


def _sample_action(probabilities: dict[OpponentAction, float], rng: Random) -> OpponentAction:
    draw = rng.random()
    cumulative = 0.0
    for action, probability in probabilities.items():
        cumulative += probability
        if draw <= cumulative:
            return action
    return next(reversed(probabilities))


def _pot_share(hero: HandScore, opponents: tuple[HandScore, ...]) -> float:
    scores = (hero, *opponents)
    best = max(scores)
    winners = sum(1 for score in scores if score == best)
    return 1.0 / winners if hero == best else 0.0


def _hero_showdown_return(
    current_pot: float,
    hero_investment: float,
    hero_score: HandScore,
    opponents: dict[int, _SimPlayer],
    continuing_scores: tuple[HandScore, ...],
) -> float:
    """Return hero's base-pot and decision-time side-pot winnings."""
    continuing_states = tuple(state for state in opponents.values() if state.reaches_showdown)
    score_by_seat = {
        state.player.seat: score
        for state, score in zip(continuing_states, continuing_scores, strict=True)
    }
    returned = _pot_share(hero_score, continuing_scores) * current_pot
    contributions: dict[int | str, float] = {
        "hero": hero_investment,
        **{state.player.seat: state.additional_investment for state in opponents.values()},
    }
    levels = sorted({amount for amount in contributions.values() if amount > 0})
    previous = 0.0
    for level in levels:
        contributors = tuple(
            participant for participant, amount in contributions.items() if amount >= level
        )
        layer = (level - previous) * len(contributors)
        previous = level
        eligible_scores: list[tuple[int | str, HandScore]] = []
        if hero_investment >= level:
            eligible_scores.append(("hero", hero_score))
        eligible_scores.extend(
            (seat, score) for seat, score in score_by_seat.items() if contributions[seat] >= level
        )
        if not eligible_scores:
            continue
        best = max(score for _, score in eligible_scores)
        winners = tuple(participant for participant, score in eligible_scores if score == best)
        if "hero" in winners:
            returned += layer / len(winners)
    return returned


def _position_fraction(order: tuple[int, ...], seat: int) -> float:
    if seat not in order or len(order) <= 1:
        return 0.5
    return order.index(seat) / (len(order) - 1)


def _prior_aggression(player: TablePlayer) -> int:
    return sum(
        1
        for action in player.previous_actions
        if "bet" in action.lower() or "raise" in action.lower()
    )


def _build_candidate_result(
    candidate: HeroCandidateAction, accumulator: _Accumulator
) -> CandidateActionResult:
    count = accumulator.count or 1
    variance = accumulator.m2 / (count - 1) if count > 1 else 0.0
    standard_error = sqrt(max(0.0, variance) / count)
    margin = 1.96 * standard_error
    return CandidateActionResult(
        candidate=candidate,
        estimated_net_ev=accumulator.mean,
        standard_error=standard_error,
        confidence_interval_low=accumulator.mean - margin,
        confidence_interval_high=accumulator.mean + margin,
        immediate_fold_probability=accumulator.immediate_folds / count,
        continue_probability=(accumulator.exactly_one + accumulator.multiple) / count,
        exactly_one_continues_probability=accumulator.exactly_one / count,
        multiple_continue_probability=accumulator.multiple / count,
        facing_raise_probability=accumulator.faced_raises / count,
        showdown_probability=accumulator.showdowns / count,
        conditional_showdown_equity=(
            accumulator.showdown_share_total / accumulator.showdowns
            if accumulator.showdowns
            else 0.0
        ),
        average_final_pot=accumulator.final_pot_total / count,
        average_hero_investment=accumulator.hero_investment_total / count,
        simulations=accumulator.count,
        assumptions=(
            "Net EV starts at the current decision; previous hero contributions are sunk.",
            "Opponent responses follow sampled hands, entered profiles, ranges, and legal actions.",
        ),
    )


def _fold_result(candidate: HeroCandidateAction, simulations: int) -> CandidateActionResult:
    return CandidateActionResult(
        candidate=candidate,
        estimated_net_ev=0.0,
        standard_error=0.0,
        confidence_interval_low=0.0,
        confidence_interval_high=0.0,
        immediate_fold_probability=0.0,
        continue_probability=0.0,
        exactly_one_continues_probability=0.0,
        multiple_continue_probability=0.0,
        facing_raise_probability=0.0,
        showdown_probability=0.0,
        conditional_showdown_equity=0.0,
        average_final_pot=0.0,
        average_hero_investment=0.0,
        simulations=simulations,
        assumptions=("Folding has zero future EV; previous contributions are already sunk.",),
    )


def _recommend(results: tuple[CandidateActionResult, ...]) -> tuple[str, str | None]:
    ordered = sorted(results, key=lambda result: result.estimated_net_ev, reverse=True)
    best = ordered[0]
    uncertainty: str | None = None
    if len(ordered) > 1:
        second = ordered[1]
        combined_error = 1.96 * sqrt(best.standard_error**2 + second.standard_error**2)
        if best.estimated_net_ev - second.estimated_net_ev <= combined_error:
            uncertainty = (
                f"{best.candidate.label} and {second.candidate.label} are statistically close "
                "under the selected policy simulation."
            )
    return best.candidate.label, uncertainty


def _raise_if_cancelled(cancel_callback: CancelCallback | None) -> None:
    if cancel_callback is not None and cancel_callback():
        raise SimulationCancelledError("Action-aware simulation was cancelled.")
