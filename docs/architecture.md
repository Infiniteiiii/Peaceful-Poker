# Architecture

Peaceful Poker separates immutable domain models, pure poker engines, orchestration services,
strategy rules, training scenarios, and PySide6 presentation code. `TableState` owns explicit
clockwise seat state and action order. The original showdown-equity engine remains independent of
the bounded action-aware simulator, which evaluates legal hero candidates with sampled opponent
hands and the rule-based policies in `resources/opponent_profiles.json`.

The UI submits validated `GameState` values and action-aware settings to an `AnalysisWorker` on a
`QThread`. A GUI-thread signal bridge receives aggregate progress across candidate actions,
analysis generation IDs reject stale work, and closing a running analysis waits asynchronously for
cancellation before the window exits. The analysis service returns raw showdown equity and
action-aware EV as separate result fields.

Candidate generation owns the common pot fractions, effective-stack cap, chip rounding, and
deduplication. The opponent policy receives both the pot before the wager and the current pot, so
bet-to-pot pressure is not diluted by Hero's own bet. The simulator classifies every iteration into
fold, unraised-call, or raise branches and returns their probabilities, conditional equities,
sampled range strengths, conditional EVs, and weighted EV components. Those components are the
single source for Advanced diagnostics, Training recommendations, and exports.

Packaged assets live under `poker_trainer/resources`. `resource_path.py` supports source, installed,
and PyInstaller paths. Settings, logs, hands, and exports use `%LOCALAPPDATA%\Peaceful Poker`, never
the source tree or executable bundle.

The presentation layer uses progressive disclosure rather than separate beginner and expert
windows. Normal mode maps hidden expert controls to documented safe defaults without deleting
their values. The result area owns a concise Overview plus nested Advanced detail views. Training
stores a generated `GameState`, builds its exact sized choices from the action-aware candidate
generator, and moves through explicit inactive, awaiting-choice, analyzing, and answer-revealed
states around the same `AnalysisWorker` used by ordinary analysis. Training session counters remain
in memory and do not alter the saved-hand schema.

`strategy/action_labels.py` is the presentation boundary for Check, Bet, Call, Raise, Fold, and
contextual all-in wording. Candidate generation, recommendations, result views, Training, and
exports consume those canonical labels. The underlying action kinds and numerical engine outputs
remain structured independently of their display text.
