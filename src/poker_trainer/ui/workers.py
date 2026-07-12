"""Qt workers for background analysis."""

from threading import Event
from typing import Any

from poker_trainer.models.action_aware import ActionAwareSettings
from poker_trainer.models.game_state import GameState
from poker_trainer.services.analysis_service import analyze_game_state


class AnalysisWorker:  # pragma: no cover - exercised through UI smoke tests
    """Small QObject-compatible worker created after PySide6 is imported."""

    def __init__(
        self,
        qtcore: Any,
        game_state: GameState,
        opponent_range: str,
        simulation_count: int,
        seed: int | None,
        action_aware_settings: ActionAwareSettings | None = None,
    ) -> None:
        """Create a QObject instance with dynamically attached signals."""
        base = qtcore.QObject

        class _Worker(base):  # type: ignore[misc, valid-type]
            progress = qtcore.Signal(int, int)
            finished = qtcore.Signal(object)
            error = qtcore.Signal(str)

            def __init__(self) -> None:
                super().__init__()
                self.cancelled = Event()

            def run(self) -> None:
                try:
                    result = analyze_game_state(
                        game_state,
                        opponent_range=opponent_range,
                        simulation_count=simulation_count,
                        seed=seed,
                        progress_callback=self.progress.emit,
                        cancel_callback=self.cancelled.is_set,
                        include_action_aware=True,
                        action_aware_settings=action_aware_settings,
                    )
                except Exception as exc:  # noqa: BLE001 - user-facing worker boundary
                    self.error.emit(str(exc))
                    return
                self.finished.emit(result)

            def cancel(self) -> None:
                self.cancelled.set()

        self.object = _Worker()
