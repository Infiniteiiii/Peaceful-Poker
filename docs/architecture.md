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

Packaged assets live under `poker_trainer/resources`. `resource_path.py` supports source, installed,
and PyInstaller paths. Settings, logs, hands, and exports use `%LOCALAPPDATA%\Peaceful Poker`, never
the source tree or executable bundle.
