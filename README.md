# Peaceful Poker

Peaceful Poker is a Windows desktop decision trainer for educational No-Limit Texas Hold'em
study. Enter a hand and betting context to inspect the current made hand, best five cards,
board texture, draws, apparent outs, final-hand probabilities, showdown equity, pot odds, and a
transparent rule-based action recommendation.

Peaceful Poker is not an online poker client, gambling service, live-game assistant, GTO solver,
or promise of profitable play. Its advice is only as reliable as the entered cards, pot, stacks,
player count, and simplified opponent-range assumption.

## Release Features

- Validated 52-card model, duplicate prevention, and custom five/seven-card evaluator
- Preflop, flop, turn, and river analysis with board-only and split-pot handling
- Draws, apparent unique outs, exact flop/turn improvement probabilities, and river final state
- Exact practical heads-up equity and seeded Monte Carlo simulation for larger state spaces
- Random, premium, tight, standard, and loose opponent assumptions
- Pot odds, required equity, simplified call EV, legal actions, and qualified recommendations
- Cancellable background analysis with stale-result protection and safe window-close cleanup
- Light/dark themes, settings, training scenarios, save/load, and Markdown/JSON export
- Original project-generated SVG/PNG/ICO application artwork
- PyInstaller one-folder Windows release and headless CI coverage

The desktop layout uses a scrollable setup/card panel on the left and analysis tabs on the right.
The overview tab presents the decision summary; the probability tab shows exact and at-least final
hand categories. Commands are arranged in two rows so the app remains usable at 900 x 620 and
common laptop resolutions.

## Requirements

- Python 3.12 or newer
- Windows 10 or newer for the packaged desktop build
- PowerShell examples below assume commands are run from the repository root

The source is developed with Python 3.14 while preserving Python 3.12 syntax and configuration.

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,build]"
```

## Launch From Source

Both commands open the same Peaceful Poker application:

```powershell
python -m poker_trainer
peaceful-poker
```

Enter both hero cards, then either no board, a complete three-card flop, a flop plus turn, or a
complete five-card board. `Current pot` includes all chips already in the middle, including the
opponent's current bet, but excludes hero's pending call. Choose **Analyze** and use **Cancel** to
stop a long simulation.

Used cards are disabled in the card picker. Manual duplicate or out-of-sequence entries produce a
clear validation message. **Clear street** removes only the latest entered community-card street;
**New hand** clears cards and stale analysis.

## Quality Checks

```powershell
python -m pytest
python -m ruff format --check .
python -m ruff check .
python -m mypy src
python -m pip check
```

For a cache-independent test pass, useful on some OneDrive folders:

```powershell
python -m pytest -p no:cacheprovider
```

## Build The Windows App

The build script installs development/build extras, runs every quality check, removes prior build
output, invokes PyInstaller, and confirms the executable exists:

```powershell
.\scripts\build_windows.ps1
```

Release output:

```text
dist\Peaceful Poker\Peaceful Poker.exe
```

Run the source checks and independent packaged-app smoke analysis with:

```powershell
.\scripts\verify.ps1
```

The packaged verification launches from a temporary directory, loads bundled themes/icon,
analyzes the default six-player hand, writes a saved hand under temporary local app data, and
closes normally. It therefore does not rely on the source repository at runtime.

## Saved Data

Normal application data is outside the installation bundle:

```text
%LOCALAPPDATA%\Peaceful Poker
```

This contains settings, logs, and default saved-hand/export locations. If `LOCALAPPDATA` is not
available, the app tries `APPDATA` and then the user's home directory.

Saved hands use the versioned JSON schema documented in `docs/save_schema.md`. Invalid JSON,
missing fields, future schema versions, invalid streets, and duplicate cards are rejected.

## Calculation Assumptions

### Opponent ranges

Presets are intentionally simple filters, not weighted solver ranges. Supported notation includes
exact pairs (`AA`), suited/offsuit holdings (`AKs`, `AQo`), pair-plus ranges (`99+`), suited-plus
ranges (`ATs+`), and pair intervals (`22-88`). Each dealt combination is filtered after known cards
are removed, so hero, board, and opponent cards cannot overlap.

### Equity

The evaluator enumerates practical completed-river and heads-up-turn state spaces exactly. Larger
or multiway states use Monte Carlo simulation. Every simulation removes known cards, deals legal
non-overlapping holdings, and uses deterministic seeds in tests. A split pot contributes hero's
fractional share, so total equity can differ from raw tie probability.

### Pot and EV

```text
Final pot after calling = current pot + amount to call
Required equity = amount to call / final pot after calling
Call EV = equity * current pot - (1 - equity) * amount to call
```

The opponent's current bet must already be included in `current pot`; it is not added a second
time. Simplified EV excludes future betting, rake, implied/reverse-implied odds, range uncertainty,
and opponent adaptation.

### Recommendations

Recommendations use packaged, reviewable thresholds plus legal actions, equity, pot odds, and
apparent outs. They are educational rules, not GTO output. Apparent outs are not guaranteed clean
against every opponent range.

## Architecture

```text
src/poker_trainer/
  engine/       Pure hand, draw, range, probability, and equity calculations
  models/       Immutable cards, game state, hand, equity, and recommendation data
  resources/    Bundled themes, configuration, and original application artwork
  services/     Analysis orchestration, persistence, exports, settings, and logging
  strategy/     Pot odds, legal actions, and transparent recommendation rules
  training/     Deterministic practice scenario generation
  ui/           PySide6 window and cancellable worker integration
```

Poker logic has no Qt dependency. `resource_path.py` resolves the same packaged assets in source,
installed, and PyInstaller environments. User writes always go through the local application-data
service rather than the source or bundle directory.

## Troubleshooting

- UI does not open: activate `.venv` and confirm `python -m pip check` passes.
- Card rejected: enter codes such as `AS`, `TH`, or `10H`, with no duplicate known cards.
- Range rejected: choose a preset or one of the documented notation forms.
- Analysis feels slow: choose **Quick**; exact turn enumeration may still take longer than Monte
  Carlo because it evaluates every legal outcome.
- Pytest cache warning in a synchronized OneDrive folder: close concurrent test processes, remove
  only `.pytest_cache`, and rerun. Use `-p no:cacheprovider` for a cache-independent verification.
- Build fails: confirm Python is 3.12+, install `.[dev,build]`, and rerun the build script from the
  repository root.

See `CHANGELOG.md`, `docs/release_checklist.md`, and the documents under `docs/` for release details.
