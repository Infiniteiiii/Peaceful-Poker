# Changelog

All notable release changes are documented here.

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
