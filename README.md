# Peaceful Poker

Peaceful Poker is an educational desktop trainer for No-Limit Texas Hold'em. It
helps users enter a hand, inspect made hands and draws, estimate showdown equity,
review pot odds, and receive transparent rule-based recommendations.

It is not an online poker client, gambling service, live-game assistant, or GTO
solver. Recommendations are educational and depend on the entered assumptions.

## Features

- Immutable card model, standard deck, duplicate-card validation, and custom hand evaluator
- Validated Hold'em game states for 2 through 10 players
- Street detection, current-hand analysis, board texture, draws, and apparent outs
- Exact final-hand probabilities on flop, turn, and river where practical
- Exact river and heads-up turn showdown equity when under the state-space threshold
- Seeded Monte Carlo equity for larger and multiway spots
- Random, premium, tight, standard, and loose opponent range assumptions
- Practical range subset: `AA`, `AKs`, `AQo`, `99+`, `ATs+`, `22-88`
- Pot odds, required equity, simplified call EV, legal actions, and recommendations
- Functional PySide6 desktop interface with background analysis and cancellation
- Versioned JSON save/load, Markdown/JSON export, settings, light/dark themes, and training mode

## Requirements

- Python 3.12 or newer
- Windows PowerShell examples below assume a local virtual environment

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
```

## Run Checks

```powershell
python -m pytest
python -m ruff format --check .
python -m ruff check .
python -m mypy src
python -m pip check
```

## Launch

```powershell
python -m poker_trainer
peaceful-poker
```

## Using The Analyzer

1. Select the active player count, hero position, blinds, stacks, current pot, and amount to call.
2. Enter or pick the two hero cards and any community cards currently visible.
3. Choose an opponent range preset and simulation accuracy.
4. Press Analyze. Long simulations run in a background worker and can be cancelled.
5. Review made hand, board texture, draws, apparent outs, equity, pot odds, and recommendation.
6. Save or export the hand if desired.

Current pot means all chips already in the middle, including the opponent's
current bet, but excluding the hero's pending call. Required equity is calculated
as `amount_to_call / (current_pot + amount_to_call)`.

## Assumptions And Limitations

Opponent ranges are simplified presets or a supported notation subset. Apparent
outs are not guaranteed clean because opponent ranges are not analyzed deeply
enough to prove cleanliness. Simplified call EV excludes future betting, rake,
implied odds, reverse implied odds, range uncertainty, and opponent adaptation.

The recommendation engine is transparent and rule-based. It does not claim to be
GTO or guaranteed profitable.

## Saved Data

Saved hands, settings, and logs are stored under the local user data directory:

```text
%LOCALAPPDATA%\Peaceful Poker
```

If `%LOCALAPPDATA%` is unavailable, Peaceful Poker falls back to the user's home
directory.

## Project Structure

```text
src/poker_trainer/
  engine/       Pure poker calculations, ranges, equity, draws, probabilities
  models/       Cards, hands, game state, equity, and recommendation models
  services/     Analysis orchestration, settings, storage, export, logging
  strategy/     Legal actions, pot odds, EV, and recommendation rules
  training/     Training scenario generation
  ui/           PySide6 main window and worker glue
```

## Benchmarks

```powershell
python scripts\benchmark_probabilities.py
python scripts\benchmark_equity.py
```

## Troubleshooting

- If the UI does not open, confirm PySide6 is installed in the active environment.
- If a card is rejected, check for duplicates across hero and board slots.
- If a range is rejected, use a preset or the supported notation subset.
- If simulations are slow, choose the Quick preset.