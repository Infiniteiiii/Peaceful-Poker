"""Main Peaceful Poker desktop window."""

from pathlib import Path
from typing import Any

from poker_trainer.models.card import Card, Rank, Suit
from poker_trainer.models.equity import SimulationPreset
from poker_trainer.models.game_state import GameState, Position
from poker_trainer.services.analysis_service import AnalysisResult
from poker_trainer.services.export_service import export_analysis_json, export_analysis_markdown
from poker_trainer.services.settings_service import UserSettings, load_settings, save_settings
from poker_trainer.services.storage_service import SavedHand, load_hand, save_hand
from poker_trainer.training.training_service import TrainingDifficulty, generate_scenario
from poker_trainer.ui.workers import AnalysisWorker

_CARD_SLOTS = ("Hero 1", "Hero 2", "Flop 1", "Flop 2", "Flop 3", "Turn", "River")
_RANGE_OPTIONS = ("random", "premium", "tight", "standard", "loose")
_PRESETS = {
    "Quick": SimulationPreset.QUICK,
    "Standard": SimulationPreset.STANDARD,
    "Accurate": SimulationPreset.ACCURATE,
    "Very Accurate": SimulationPreset.VERY_ACCURATE,
}


class MainWindow:  # pragma: no cover - Qt smoke-tested through app startup
    """Factory wrapper that builds a concrete QMainWindow after PySide import."""

    def __init__(self, qtwidgets: Any, qtcore: Any) -> None:
        """Create the concrete Qt window object."""
        self.qtwidgets = qtwidgets
        self.qtcore = qtcore
        self.settings = load_settings()
        self.latest_result: AnalysisResult | None = None
        self.analysis_id = 0
        self.thread: Any | None = None
        self.worker: Any | None = None
        self.window = qtwidgets.QMainWindow()
        self.window.setWindowTitle("Peaceful Poker")
        self.window.resize(1180, 760)
        self._build()
        self._apply_theme(self.settings.theme)

    def show(self) -> None:
        """Show the concrete Qt window."""
        self.window.show()

    def _build(self) -> None:
        central = self.qtwidgets.QWidget()
        root = self.qtwidgets.QVBoxLayout(central)
        splitter = self.qtwidgets.QSplitter()
        splitter.addWidget(self._setup_panel())
        splitter.addWidget(self._results_panel())
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter)
        root.addLayout(self._button_row())
        self.window.setCentralWidget(central)

    def _setup_panel(self) -> Any:
        panel = self.qtwidgets.QWidget()
        layout = self.qtwidgets.QFormLayout(panel)
        self.players = self.qtwidgets.QSpinBox()
        self.players.setRange(2, 10)
        self.players.setValue(self.settings.default_player_count)
        self.position = self.qtwidgets.QComboBox()
        for position in Position:
            self.position.addItem(position.display_name, position.value)
        self.small_blind = self._money_spin(self.settings.small_blind)
        self.big_blind = self._money_spin(self.settings.big_blind)
        self.ante = self._money_spin(0.0)
        self.pot = self._money_spin(140.0)
        self.call = self._money_spin(40.0)
        self.stack = self._money_spin(900.0)
        self.effective = self._money_spin(620.0)
        self.previous_action = self.qtwidgets.QComboBox()
        self.previous_action.addItems(["None", "Checked to hero", "Bet to hero", "Raised to hero"])
        self.range_combo = self.qtwidgets.QComboBox()
        self.range_combo.addItems(list(_RANGE_OPTIONS))
        self.preset_combo = self.qtwidgets.QComboBox()
        self.preset_combo.addItems(list(_PRESETS))
        self.auto_analysis = self.qtwidgets.QCheckBox("Analyze automatically")
        self.auto_analysis.setChecked(self.settings.automatic_analysis)
        for label, widget in (
            ("Active players", self.players),
            ("Hero position", self.position),
            ("Small blind", self.small_blind),
            ("Big blind", self.big_blind),
            ("Ante", self.ante),
            ("Current pot", self.pot),
            ("Amount to call", self.call),
            ("Hero stack", self.stack),
            ("Effective stack", self.effective),
            ("Previous action", self.previous_action),
            ("Opponent range", self.range_combo),
            ("Simulation accuracy", self.preset_combo),
            ("Mode", self.auto_analysis),
        ):
            layout.addRow(label, widget)
        self.card_edits: list[Any] = []
        for slot in _CARD_SLOTS:
            row = self.qtwidgets.QHBoxLayout()
            edit = self.qtwidgets.QLineEdit()
            edit.setPlaceholderText("AS")
            edit.setAccessibleName(slot)
            pick = self.qtwidgets.QPushButton("Pick")
            clear = self.qtwidgets.QPushButton("Clear")
            pick.clicked.connect(lambda _checked=False, field=edit: self._pick_card(field))
            clear.clicked.connect(lambda _checked=False, field=edit: field.clear())
            row.addWidget(edit)
            row.addWidget(pick)
            row.addWidget(clear)
            layout.addRow(slot, row)
            self.card_edits.append(edit)
        self.card_edits[0].setText("AS")
        self.card_edits[1].setText("KS")
        self.card_edits[2].setText("QS")
        self.card_edits[3].setText("10D")
        self.card_edits[4].setText("4S")
        return panel

    def _results_panel(self) -> Any:
        panel = self.qtwidgets.QWidget()
        layout = self.qtwidgets.QVBoxLayout(panel)
        self.progress = self.qtwidgets.QProgressBar()
        self.output = self.qtwidgets.QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.progress)
        layout.addWidget(self.output)
        return panel

    def _button_row(self) -> Any:
        row = self.qtwidgets.QHBoxLayout()
        self.analyze_button = self.qtwidgets.QPushButton("Analyze")
        self.cancel_button = self.qtwidgets.QPushButton("Cancel analysis")
        self.cancel_button.setEnabled(False)
        buttons = [
            self.analyze_button,
            self.cancel_button,
            self.qtwidgets.QPushButton("Clear current street"),
            self.qtwidgets.QPushButton("New hand"),
            self.qtwidgets.QPushButton("Save hand"),
            self.qtwidgets.QPushButton("Load hand"),
            self.qtwidgets.QPushButton("Export analysis"),
            self.qtwidgets.QPushButton("Settings"),
            self.qtwidgets.QPushButton("Training mode"),
            self.qtwidgets.QPushButton("Help/About"),
        ]
        for button in buttons:
            row.addWidget(button)
        self.analyze_button.clicked.connect(self.analyze)
        self.cancel_button.clicked.connect(self.cancel)
        buttons[2].clicked.connect(self.clear_current_street)
        buttons[3].clicked.connect(self.new_hand)
        buttons[4].clicked.connect(self.save)
        buttons[5].clicked.connect(self.load)
        buttons[6].clicked.connect(self.export)
        buttons[7].clicked.connect(self.settings_dialog)
        buttons[8].clicked.connect(self.training)
        buttons[9].clicked.connect(self.about)
        return row

    def _money_spin(self, value: float) -> Any:
        spin = self.qtwidgets.QDoubleSpinBox()
        spin.setRange(0.0, 1_000_000.0)
        spin.setDecimals(2)
        spin.setValue(value)
        return spin

    def _state(self) -> GameState:
        hero = tuple(Card.from_code(edit.text()) for edit in self.card_edits[:2])
        board = tuple(
            Card.from_code(edit.text()) for edit in self.card_edits[2:] if edit.text().strip()
        )
        return GameState(
            active_players=int(self.players.value()),
            hero_cards=hero,
            community_cards=board,
            hero_position=Position(str(self.position.currentData())),
            pot_size=float(self.pot.value()),
            amount_to_call=float(self.call.value()),
            hero_stack=float(self.stack.value()),
            effective_stack=float(self.effective.value()),
            small_blind=float(self.small_blind.value()),
            big_blind=float(self.big_blind.value()),
            ante=float(self.ante.value()),
            previous_action=str(self.previous_action.currentText()),
            requested_simulation_count=_PRESETS[str(self.preset_combo.currentText())],
        )

    def analyze(self) -> None:
        """Start background analysis."""
        try:
            state = self._state()
        except Exception as exc:  # noqa: BLE001 - user-facing validation boundary
            self.output.setText(str(exc))
            return
        self.analysis_id += 1
        current_id = self.analysis_id
        self.progress.setValue(0)
        self.analyze_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.thread = self.qtcore.QThread()
        factory = AnalysisWorker(
            self.qtcore,
            state,
            str(self.range_combo.currentText()),
            _PRESETS[str(self.preset_combo.currentText())],
            7,
        )
        self.worker = factory.object
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._progress)
        self.worker.finished.connect(lambda result: self._finished(result, current_id))
        self.worker.error.connect(self._error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)
        self.thread.finished.connect(self._thread_finished)
        self.thread.start()

    def cancel(self) -> None:
        """Request cancellation for the active worker."""
        if self.worker is not None:
            self.worker.cancel()

    def _progress(self, current: int, total: int) -> None:
        self.progress.setMaximum(max(total, 1))
        self.progress.setValue(current)

    def _finished(self, result: object, analysis_id: int) -> None:
        if analysis_id != self.analysis_id:
            return
        self.latest_result = result if isinstance(result, AnalysisResult) else None
        if self.latest_result is not None:
            self.output.setText(_format_result(self.latest_result))

    def _error(self, message: str) -> None:
        self.output.setText(message)

    def _thread_finished(self) -> None:
        self.analyze_button.setEnabled(True)
        self.cancel_button.setEnabled(False)

    def _pick_card(self, field: Any) -> None:
        dialog = self.qtwidgets.QDialog(self.window)
        dialog.setWindowTitle("Select card")
        grid = self.qtwidgets.QGridLayout(dialog)
        used = {edit.text().strip().upper() for edit in self.card_edits if edit is not field}
        for row, rank in enumerate(reversed(tuple(Rank))):
            for col, suit in enumerate(Suit):
                card = Card(rank, suit)
                button = self.qtwidgets.QPushButton(card.short_code)
                button.setAccessibleName(card.display_name)
                button.setEnabled(card.code not in used and card.short_code not in used)
                button.clicked.connect(
                    lambda _checked=False, c=card: self._set_card(dialog, field, c)
                )
                grid.addWidget(button, row, col)
        dialog.exec()

    def _set_card(self, dialog: Any, field: Any, card: Card) -> None:
        field.setText(card.code)
        dialog.accept()

    def clear_current_street(self) -> None:
        for edit in self.card_edits[2:]:
            edit.clear()

    def new_hand(self) -> None:
        for edit in self.card_edits:
            edit.clear()
        self.output.clear()

    def save(self) -> None:
        path_text, _filter = self.qtwidgets.QFileDialog.getSaveFileName(
            self.window, "Save hand", "", "JSON Files (*.json)"
        )
        if path_text:
            summary = self.output.toPlainText() if self.latest_result else None
            save_hand(
                SavedHand(self._state(), str(self.range_combo.currentText()), "", summary),
                Path(path_text),
            )

    def load(self) -> None:
        path_text, _filter = self.qtwidgets.QFileDialog.getOpenFileName(
            self.window, "Load hand", "", "JSON Files (*.json)"
        )
        if path_text:
            hand = load_hand(Path(path_text))
            self._apply_state(hand.game_state)
            self.range_combo.setCurrentText(hand.opponent_range)

    def export(self) -> None:
        if self.latest_result is None:
            self.output.setText("Run analysis before exporting.")
            return
        path_text, _filter = self.qtwidgets.QFileDialog.getSaveFileName(
            self.window, "Export analysis", "", "Markdown (*.md);;JSON (*.json)"
        )
        if path_text:
            path = Path(path_text)
            if path.suffix.lower() == ".json":
                export_analysis_json(self.latest_result, path)
            else:
                export_analysis_markdown(self.latest_result, path)

    def settings_dialog(self) -> None:
        theme = "dark" if self.settings.theme == "light" else "light"
        self.settings = UserSettings(theme=theme, automatic_analysis=self.auto_analysis.isChecked())
        save_settings(self.settings)
        self._apply_theme(theme)

    def training(self) -> None:
        scenario = generate_scenario(TrainingDifficulty.BEGINNER, seed=11)
        self._apply_state(scenario.game_state)
        self.latest_result = scenario.analysis
        self.output.setText(
            "Training mode: choose from legal actions first: "
            + ", ".join(scenario.legal_action_labels)
            + "\n\n"
            + _format_result(scenario.analysis)
        )

    def about(self) -> None:
        self.qtwidgets.QMessageBox.information(
            self.window,
            "Peaceful Poker",
            "Peaceful Poker is an educational No-Limit Texas Hold'em trainer. "
            "Recommendations are rule-based and not guaranteed profitable.",
        )

    def _apply_state(self, state: GameState) -> None:
        self.players.setValue(state.active_players)
        self.position.setCurrentText(state.hero_position.display_name)
        self.small_blind.setValue(state.small_blind)
        self.big_blind.setValue(state.big_blind)
        self.ante.setValue(state.ante)
        self.pot.setValue(state.pot_size)
        self.call.setValue(state.amount_to_call)
        self.stack.setValue(state.hero_stack)
        self.effective.setValue(state.effective_stack)
        values = [*state.hero_cards, *state.community_cards]
        for index, edit in enumerate(self.card_edits):
            edit.setText(values[index].code if index < len(values) else "")

    def _apply_theme(self, theme: str) -> None:
        if theme == "dark":
            self.window.setStyleSheet("QWidget { background: #202124; color: #f1f3f4; }")
        else:
            self.window.setStyleSheet("")


def _format_result(result: AnalysisResult) -> str:
    best_five = " ".join(card.code for card in result.current_hand.best_five_cards) or "Preflop"
    draws = ", ".join(draw.description for draw in result.draws) or "None"
    win_tie_loss = (
        f"Win/Tie/Loss: {result.equity.win_percentage:.1%} / "
        f"{result.equity.tie_percentage:.1%} / {result.equity.loss_percentage:.1%}"
    )
    calculation = (
        f"Calculation: {result.equity.calculation_method} "
        f"({result.equity.iterations} iterations/outcomes)"
    )
    recommendation = (
        f"Recommendation: {result.recommendation.primary_action} "
        f"({result.recommendation.confidence.value})"
    )
    return "\n".join(
        [
            f"Street: {result.game_state.street.display_name}",
            f"Current hand: {result.current_hand.description}",
            f"Best five: {best_five}",
            f"Hero cards used: {result.current_hand.hero_cards_used}",
            f"Board texture: {result.board_analysis.overall_texture.value}",
            f"Draws: {draws}",
            f"Apparent outs: {len(result.outs.unique_outs)}",
            win_tie_loss,
            f"Total equity: {result.equity.total_equity:.1%}",
            calculation,
            f"Required equity: {result.pot_odds.required_equity:.1%}",
            f"Simplified EV: {result.pot_odds.simplified_call_ev}",
            recommendation,
            "Reasons: " + "; ".join(result.recommendation.reasons),
            "Risks: " + "; ".join(result.recommendation.risks),
            "Assumptions: " + "; ".join(result.recommendation.assumptions),
            result.recommendation.explanation,
        ]
    )
