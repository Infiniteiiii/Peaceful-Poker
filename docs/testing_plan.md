# Release Testing Plan

The release suite covers card/deck invariants, every hand category and tie-break path, ace-low
straights, game-state validation, street progression, board texture, draws, outs, probability
normalization, range legality, exact and seeded Monte Carlo equity, fractional splits, pot odds,
legal recommendations, persistence, exports, settings, training, UI startup, background completion,
cancellation, stale-result rejection, and close-time thread cleanup.

GitHub Actions runs the suite plus Ruff, strict Mypy, and `pip check` on Windows with Python 3.12,
3.13, and 3.14 using Qt's offscreen platform.
