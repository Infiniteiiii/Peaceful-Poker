# Changelog

All notable release changes are documented here.

## 1.1.0 - 2026-07-12

- Added explicit two-to-ten-seat table state, heads-up blind rules, clockwise street order,
  folded/all-in skipping, players-behind tracking, and action reopening after raises.
- Added nine readable opponent behavior profiles with range, hand-strength, bet-size, position,
  stack-depth, board-texture, and prior-aggression inputs.
- Added bounded action-aware Monte Carlo evaluation of every legal hero action and practical size,
  reporting net EV, confidence intervals, folds, continuations, raises, showdown frequency,
  conditional equity, final pot, and new investment.
- Preserved raw all-showdown equity as a separate result and clarified equity versus expected value.
- Added table controls, a per-seat editor, live action order, EV results, action-aware training,
  schema 1 migration, and schema 2 seat persistence.
- Added deterministic action-order, policy, EV-accounting, migration, UI, reproducibility,
  cancellation, and players-behind tests plus focused policy benchmarks.

## 1.0.0 - 2026-07-11

- Completed the custom Hold'em evaluator, draw/outs analysis, exact final-hand probabilities,
  exact/Monte Carlo equity, range filtering, pot odds, EV, and legal recommendation systems.
- Added the complete PySide6 desktop workflow with responsive controls, accessible card entry,
  settings, themes, training, persistence, exports, progress, cancellation, and safe thread cleanup.
- Added known-opponent validation, fractional multiway split equity, deterministic simulations,
  all-in-call recommendations, stale-result prevention, and regression coverage.
- Added a direct, evaluator-cross-checked hand scoring path that reduced the measured 25,000-hand
  simulation from 73.88 seconds to 5.42 seconds on the release audit machine.
- Added original Peaceful Poker vector/raster/Windows icon assets and bundled resource resolution.
- Added PyInstaller one-folder packaging, Windows version metadata, build/verification scripts,
  Python 3.12-3.14 GitHub Actions checks, benchmarks, release documentation, and packaged smoke
  analysis.
