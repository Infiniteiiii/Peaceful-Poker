# Poker Decision Trainer

Educational No-Limit Texas Hold'em decision trainer.

This repository is being built incrementally from the project specification. The
current stage focuses on the independent poker engine foundation:

- Project and package structure
- Card and deck models
- Custom five-card and seven-card hand evaluator
- Unit tests for card validation, deck behavior, hand categories, and tie-breaks

The recommendation interface, draw detector, equity engine, saving, and training
mode will be added only after the core evaluator is verified.

## Requirements

- Python 3.12 or newer
- Development dependencies from `pyproject.toml`

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
```

## Run Tests

```powershell
python -m pytest
```

## Run the Application Shell

```powershell
python -m poker_trainer
```

The current graphical shell is intentionally minimal and labelled as a
development build while engine work is underway.
