# Architecture

Peaceful Poker separates immutable domain models, pure poker engines, orchestration services,
strategy rules, training scenarios, and PySide6 presentation code.

The UI submits validated `GameState` values to an `AnalysisWorker` on a `QThread`. A GUI-thread
signal bridge receives progress/results, analysis generation IDs reject stale work, and closing a
running analysis waits asynchronously for cancellation before the window exits.

Packaged assets live under `poker_trainer/resources`. `resource_path.py` supports source, installed,
and PyInstaller paths. Settings, logs, hands, and exports use `%LOCALAPPDATA%\Peaceful Poker`, never
the source tree or executable bundle.
