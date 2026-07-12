"""Main Peaceful Poker desktop window."""

from dataclasses import replace
from pathlib import Path
from typing import Any

from poker_trainer.engine.action_aware_simulator import action_aware_preset
from poker_trainer.models.action_aware import (
    OpponentProfile,
    TablePlayer,
    TableState,
    create_default_table,
)
from poker_trainer.models.card import Card, Rank, Suit
from poker_trainer.models.equity import SimulationPreset
from poker_trainer.models.game_state import GameState, Position, street_from_board_length
from poker_trainer.models.hand import HandCategory
from poker_trainer.resource_path import resource_path
from poker_trainer.services.analysis_service import AnalysisResult
from poker_trainer.services.export_service import export_analysis_json, export_analysis_markdown
from poker_trainer.services.settings_service import UserSettings, load_settings, save_settings
from poker_trainer.services.storage_service import SavedHand, load_hand, save_hand, user_data_dir
from poker_trainer.strategy.legal_actions import legal_actions
from poker_trainer.training.training_service import (
    TrainingDifficulty,
    generate_training_state,
)
from poker_trainer.ui.workers import AnalysisWorker

_CARD_SLOTS = ("Hero card 1", "Hero card 2", "Flop 1", "Flop 2", "Flop 3", "Turn", "River")
_RANGE_OPTIONS = ("random", "premium", "tight", "standard", "loose")
_PRESETS = {
    "Quick": SimulationPreset.QUICK,
    "Standard": SimulationPreset.STANDARD,
    "Accurate": SimulationPreset.ACCURATE,
    "Very Accurate": SimulationPreset.VERY_ACCURATE,
}
_ACTION_PRESETS = ("Quick", "Standard", "Accurate")
_EMPTY_RESULT = "Enter two hero cards and a valid board, then choose Analyze."


class MainWindow:  # pragma: no cover - behavior covered through Qt integration tests
    """Build and coordinate the concrete Qt main window."""

    def __init__(self, qtwidgets: Any, qtcore: Any, qtgui: Any | None = None) -> None:
        self.qtwidgets = qtwidgets
        self.qtcore = qtcore
        self.qtgui = qtgui
        self.startup_warning: str | None = None
        try:
            self.settings = load_settings()
        except Exception as exc:  # noqa: BLE001 - recover from damaged user settings
            self.settings = UserSettings()
            self.startup_warning = f"Settings could not be loaded; defaults are active. {exc}"
        self.latest_result: AnalysisResult | None = None
        self.analysis_id = 0
        self.thread: Any | None = None
        self.worker: Any | None = None
        self.signal_bridge: Any | None = None
        self.training_prompt: str | None = None
        self.close_pending = False
        self.player_overrides: dict[int, TablePlayer] = {}
        self._suspend_changes = True
        owner = self

        class _Window(qtwidgets.QMainWindow):  # type: ignore[misc]
            def closeEvent(self, event: Any) -> None:  # noqa: N802 - Qt API
                owner._close_event(event)

        self.window = _Window()
        self.window.setObjectName("mainWindow")
        self.window.setWindowTitle("Peaceful Poker")
        self.window.setMinimumSize(900, 620)
        self.window.resize(1180, 760)
        icon_path = resource_path("peaceful_poker.ico")
        if qtgui is not None and icon_path.exists():
            self.window.setWindowIcon(qtgui.QIcon(str(icon_path)))
        self._auto_timer = qtcore.QTimer(self.window)
        self._auto_timer.setSingleShot(True)
        self._auto_timer.setInterval(600)
        self._auto_timer.timeout.connect(self._run_automatic_analysis)
        self._build()
        self._restore_geometry()
        self._apply_theme(self.settings.theme)
        self._connect_inputs()
        self._suspend_changes = False
        self._sync_button_states()
        if self.startup_warning:
            self.output.setPlainText(self.startup_warning)

    def show(self) -> None:
        """Show the concrete Qt window."""
        self.window.show()

    def _build(self) -> None:
        central = self.qtwidgets.QWidget()
        root = self.qtwidgets.QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)
        splitter = self.qtwidgets.QSplitter()
        splitter.addWidget(self._setup_panel())
        splitter.addWidget(self._results_panel())
        splitter.setSizes([430, 720])
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)
        root.addLayout(self._button_grid())
        self.window.setCentralWidget(central)

    def _setup_panel(self) -> Any:
        content = self.qtwidgets.QWidget()
        outer = self.qtwidgets.QVBoxLayout(content)
        game_group = self.qtwidgets.QGroupBox("Game setup")
        game = self.qtwidgets.QFormLayout(game_group)
        self.players = self.qtwidgets.QSpinBox()
        self.players.setRange(2, 10)
        self.players.setValue(self.settings.default_player_count)
        self.position = self.qtwidgets.QComboBox()
        for position in Position:
            self.position.addItem(position.display_name, position.value)
        self.position.setCurrentText(Position.BUTTON.display_name)
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
        self.profile_combo = self.qtwidgets.QComboBox()
        for profile in OpponentProfile:
            self.profile_combo.addItem(profile.display_name, profile.value)
        self.preset_combo = self.qtwidgets.QComboBox()
        self.preset_combo.addItems(list(_PRESETS))
        default_preset = next(
            (
                name
                for name, count in _PRESETS.items()
                if count == self.settings.default_simulation_count
            ),
            "Standard",
        )
        self.preset_combo.setCurrentText(default_preset)
        self.action_preset_combo = self.qtwidgets.QComboBox()
        self.action_preset_combo.addItems(list(_ACTION_PRESETS))
        self.players_behind = self.qtwidgets.QSpinBox()
        self.players_behind.setRange(0, max(0, self.settings.default_player_count - 1))
        self.folded_seats = self.qtwidgets.QLineEdit()
        self.folded_seats.setPlaceholderText("e.g. 2, 4")
        self.called_seats = self.qtwidgets.QLineEdit()
        self.called_seats.setPlaceholderText("e.g. 1, 3")
        self.aggressor_seat = self.qtwidgets.QSpinBox()
        self.aggressor_seat.setRange(-1, 9)
        self.aggressor_seat.setSpecialValueText("None")
        self.current_actor_seat = self.qtwidgets.QSpinBox()
        self.current_actor_seat.setRange(-1, 9)
        self.current_actor_seat.setSpecialValueText("Hero")
        self.action_order_label = self.qtwidgets.QLabel("Action order: calculating...")
        self.action_order_label.setWordWrap(True)
        self.advanced_opponents = self.qtwidgets.QPushButton("Edit individual opponents")
        self.auto_analysis = self.qtwidgets.QCheckBox("Analyze automatically after changes")
        self.auto_analysis.setChecked(self.settings.automatic_analysis)
        setup_rows = (
            (
                "Active players",
                self.players,
                "Total players still active in the hand, including hero.",
            ),
            ("Hero position", self.position, "Hero's table position."),
            ("Small blind", self.small_blind, "Small blind size in chips."),
            ("Big blind", self.big_blind, "Big blind size in chips."),
            ("Ante", self.ante, "Ante paid per player, if any."),
            (
                "Current pot",
                self.pot,
                "All chips in the middle, including the current opponent bet, "
                "excluding hero's pending call.",
            ),
            ("Amount to call", self.call, "Additional chips hero must put in to continue."),
            ("Hero stack", self.stack, "Hero's remaining stack before the decision."),
            ("Effective stack", self.effective, "Smallest relevant remaining stack."),
            ("Previous action", self.previous_action, "Most recent action facing hero."),
            ("Opponent range", self.range_combo, "Simplified opponent holding assumption."),
            (
                "Opponent profile",
                self.profile_combo,
                "Default transparent behavior profile for opponents.",
            ),
            (
                "Simulation accuracy",
                self.preset_combo,
                "Monte Carlo iteration count when exact enumeration is impractical.",
            ),
            (
                "Action-aware accuracy",
                self.action_preset_combo,
                "Policy simulations per candidate action.",
            ),
            (
                "Players behind hero",
                self.players_behind,
                "Opponents still eligible to act after hero in this betting round.",
            ),
            (
                "Folded seat numbers",
                self.folded_seats,
                "Comma-separated zero-based seats that have folded.",
            ),
            (
                "Called seat numbers",
                self.called_seats,
                "Comma-separated seats that called before hero.",
            ),
            (
                "Bettor / raiser seat",
                self.aggressor_seat,
                "Seat responsible for the current amount to call, or None.",
            ),
            (
                "Current actor seat",
                self.current_actor_seat,
                "Use Hero for analysis; another seat can be represented but must act first.",
            ),
        )
        for label, widget, tooltip in setup_rows:
            widget.setToolTip(tooltip)
            game.addRow(label, widget)
        game.addRow("Analysis mode", self.auto_analysis)
        game.addRow("Advanced table", self.advanced_opponents)
        game.addRow("Order", self.action_order_label)
        outer.addWidget(game_group)

        cards_group = self.qtwidgets.QGroupBox("Cards")
        cards = self.qtwidgets.QFormLayout(cards_group)
        self.card_edits: list[Any] = []
        for slot in _CARD_SLOTS:
            row = self.qtwidgets.QHBoxLayout()
            edit = self.qtwidgets.QLineEdit()
            edit.setPlaceholderText("AS")
            edit.setMaxLength(3)
            edit.setAccessibleName(slot)
            edit.setToolTip(f"Enter {slot.lower()} as AS, TH, or 10H.")
            pick = self.qtwidgets.QPushButton("Pick")
            pick.setToolTip(f"Choose {slot.lower()} from the deck.")
            clear = self.qtwidgets.QToolButton()
            clear.setText("X")
            clear.setToolTip(f"Clear {slot.lower()}.")
            clear.setAccessibleName(f"Clear {slot}")
            pick.clicked.connect(lambda _checked=False, field=edit: self._pick_card(field))
            clear.clicked.connect(lambda _checked=False, field=edit: field.clear())
            row.addWidget(edit, 1)
            row.addWidget(pick)
            row.addWidget(clear)
            cards.addRow(slot, row)
            self.card_edits.append(edit)
        outer.addWidget(cards_group)
        outer.addStretch(1)
        scroll = self.qtwidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(self.qtwidgets.QFrame.Shape.NoFrame)
        scroll.setWidget(content)
        scroll.setMinimumWidth(370)
        return scroll

    def _results_panel(self) -> Any:
        panel = self.qtwidgets.QWidget()
        layout = self.qtwidgets.QVBoxLayout(panel)
        self.status_label = self.qtwidgets.QLabel("Ready")
        self.status_label.setWordWrap(True)
        self.progress = self.qtwidgets.QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setFormat("Ready")
        self.tabs = self.qtwidgets.QTabWidget()
        self.output = self.qtwidgets.QTextEdit()
        self.output.setReadOnly(True)
        self.output.setLineWrapMode(self.qtwidgets.QTextEdit.LineWrapMode.WidgetWidth)
        self.output.setPlainText(_EMPTY_RESULT)
        self.probability_table = self.qtwidgets.QTableWidget(len(HandCategory), 3)
        self.probability_table.setHorizontalHeaderLabels(["Final category", "Exact", "At least"])
        self.probability_table.verticalHeader().setVisible(False)
        self.probability_table.setEditTriggers(
            self.qtwidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.probability_table.horizontalHeader().setSectionResizeMode(
            0, self.qtwidgets.QHeaderView.ResizeMode.Stretch
        )
        self.probability_table.horizontalHeader().setSectionResizeMode(
            1, self.qtwidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        self.probability_table.horizontalHeader().setSectionResizeMode(
            2, self.qtwidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        self._clear_probability_table()
        self.action_table = self.qtwidgets.QTableWidget(0, 8)
        self.action_table.setHorizontalHeaderLabels(
            [
                "Action",
                "Net EV",
                "95% CI",
                "All fold",
                "One continues",
                "Multiple",
                "Faces raise",
                "Called equity",
            ]
        )
        self.action_table.verticalHeader().setVisible(False)
        self.action_table.setEditTriggers(
            self.qtwidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.action_table.horizontalHeader().setSectionResizeMode(
            0, self.qtwidgets.QHeaderView.ResizeMode.Stretch
        )
        for column in range(1, 8):
            self.action_table.horizontalHeader().setSectionResizeMode(
                column, self.qtwidgets.QHeaderView.ResizeMode.ResizeToContents
            )
        self.tabs.addTab(self.output, "Overview")
        self.tabs.addTab(self.probability_table, "Final hand probabilities")
        self.tabs.addTab(self.action_table, "Action-aware EV")
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress)
        layout.addWidget(self.tabs, 1)
        return panel

    def _button_grid(self) -> Any:
        grid = self.qtwidgets.QGridLayout()
        self.analyze_button = self._button("Analyze", "Alt+A", "Run the complete analysis.")
        self.analyze_button.setObjectName("primaryButton")
        self.cancel_button = self._button("Cancel", "Esc", "Cancel the active calculation.")
        self.clear_button = self._button(
            "Clear street", "", "Clear the latest entered board street."
        )
        self.new_button = self._button("New hand", "Ctrl+N", "Clear cards and analysis results.")
        self.save_button = self._button("Save", "Ctrl+S", "Save the current hand as JSON.")
        self.load_button = self._button("Load", "Ctrl+O", "Load a saved Peaceful Poker hand.")
        self.export_button = self._button("Export", "Ctrl+E", "Export the latest analysis.")
        self.settings_button = self._button("Settings", "", "Change theme and analysis defaults.")
        self.training_button = self._button("Training", "", "Load a generated practice scenario.")
        self.about_button = self._button(
            "Help / About", "F1", "Show application and limitation information."
        )
        buttons = (
            self.analyze_button,
            self.cancel_button,
            self.clear_button,
            self.new_button,
            self.save_button,
            self.load_button,
            self.export_button,
            self.settings_button,
            self.training_button,
            self.about_button,
        )
        for index, button in enumerate(buttons):
            grid.addWidget(button, index // 5, index % 5)
        self.analyze_button.clicked.connect(self.analyze)
        self.cancel_button.clicked.connect(self.cancel)
        self.clear_button.clicked.connect(self.clear_current_street)
        self.new_button.clicked.connect(self.new_hand)
        self.save_button.clicked.connect(self.save)
        self.load_button.clicked.connect(self.load)
        self.export_button.clicked.connect(self.export)
        self.settings_button.clicked.connect(self.settings_dialog)
        self.training_button.clicked.connect(self.training)
        self.about_button.clicked.connect(self.about)
        return grid

    def _button(self, text: str, shortcut: str, tooltip: str) -> Any:
        button = self.qtwidgets.QPushButton(text)
        if shortcut:
            button.setShortcut(shortcut)
        button.setToolTip(tooltip)
        return button

    def _money_spin(self, value: float) -> Any:
        spin = self.qtwidgets.QDoubleSpinBox()
        spin.setRange(0.0, 1_000_000.0)
        spin.setDecimals(2)
        spin.setValue(value)
        spin.setSuffix(" chips")
        return spin

    def _connect_inputs(self) -> None:
        for widget in (
            self.players,
            self.players_behind,
            self.aggressor_seat,
            self.current_actor_seat,
            self.small_blind,
            self.big_blind,
            self.ante,
            self.pot,
            self.call,
            self.stack,
            self.effective,
        ):
            widget.valueChanged.connect(self._input_changed)
        for widget in (
            self.position,
            self.previous_action,
            self.range_combo,
            self.profile_combo,
            self.preset_combo,
            self.action_preset_combo,
        ):
            widget.currentIndexChanged.connect(self._input_changed)
        for edit in (*self.card_edits, self.folded_seats, self.called_seats):
            edit.textChanged.connect(self._input_changed)
        self.players.valueChanged.connect(self._player_count_changed)
        self.advanced_opponents.clicked.connect(self.opponent_editor)
        self.auto_analysis.toggled.connect(self._auto_analysis_changed)
        self._update_action_order()

    def _state(self) -> GameState:
        hero_text = [edit.text().strip() for edit in self.card_edits[:2]]
        if not all(hero_text):
            raise ValueError("Enter both hero cards before analyzing.")
        board_text = [edit.text().strip() for edit in self.card_edits[2:]]
        if any(board_text[:3]) and not all(board_text[:3]):
            raise ValueError("Enter all three flop cards, or clear the flop.")
        if board_text[3] and not all(board_text[:3]):
            raise ValueError("Enter the complete flop before the turn.")
        if board_text[4] and not board_text[3]:
            raise ValueError("Enter the turn before the river.")
        hero = tuple(Card.from_code(text) for text in hero_text)
        board = tuple(Card.from_code(text) for text in board_text if text)
        street = street_from_board_length(len(board))
        table_state = self._build_table_state(street.value)
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
            table_state=table_state,
        )

    def _build_table_state(self, street: str) -> TableState:
        player_count = int(self.players.value())
        hero_position = Position(str(self.position.currentData()))
        base = create_default_table(
            player_count,
            hero_position.value,
            street,
            float(self.stack.value()),
            float(self.effective.value()),
        )
        folded = self._parse_seats(self.folded_seats.text(), player_count, "folded")
        called = self._parse_seats(self.called_seats.text(), player_count, "called")
        aggressor = int(self.aggressor_seat.value())
        if aggressor >= player_count:
            raise ValueError("The bettor/raiser seat is outside the active table.")
        clockwise_opponents = tuple(
            player.seat for player in base.clockwise_after(base.hero_seat) if not player.is_hero
        )
        behind_count = min(int(self.players_behind.value()), len(clockwise_opponents))
        behind = set(clockwise_opponents[:behind_count])
        default_profile = OpponentProfile(str(self.profile_combo.currentData()))
        players: list[TablePlayer] = []
        for player in base.players:
            if player.is_hero:
                players.append(player)
                continue
            is_folded = player.seat in folded
            is_called = player.seat in called
            is_aggressor = player.seat == aggressor
            acted = player.seat not in behind or is_called or is_aggressor
            previous_actions: tuple[str, ...] = ()
            if is_called:
                previous_actions = ("Called",)
            elif is_aggressor:
                previous_actions = ("Raised",)
            elif acted:
                previous_actions = ("Checked",)
            contribution = (
                float(self.call.value()) if is_called or is_aggressor else player.round_contribution
            )
            configured = replace(
                player,
                folded=is_folded,
                eligible_to_act=not is_folded,
                profile=default_profile,
                range_text=str(self.range_combo.currentText()),
                previous_actions=previous_actions,
                acted_this_round=acted,
                round_contribution=contribution,
                total_contribution=max(player.total_contribution, contribution),
            )
            override = self.player_overrides.get(player.seat)
            if override:
                configured = replace(
                    configured,
                    position=override.position,
                    folded=override.folded,
                    all_in=override.all_in,
                    stack=override.stack,
                    profile=override.profile,
                    range_text=override.range_text,
                    previous_actions=override.previous_actions,
                    eligible_to_act=override.eligible_to_act,
                    acted_this_round=override.acted_this_round,
                )
            players.append(configured)
        selected_actor = int(self.current_actor_seat.value())
        current_actor = base.hero_seat if selected_actor < 0 else selected_actor
        if current_actor >= player_count:
            raise ValueError("The current actor seat is outside the active table.")
        return replace(base, players=tuple(players), current_actor_seat=current_actor)

    def _parse_seats(self, text: str, player_count: int, label: str) -> set[int]:
        if not text.strip():
            return set()
        try:
            seats = {int(part.strip()) for part in text.split(",") if part.strip()}
        except ValueError as exc:
            raise ValueError(
                f"The {label} seat list must contain comma-separated numbers."
            ) from exc
        if any(seat < 0 or seat >= player_count for seat in seats):
            raise ValueError(f"A {label} seat is outside the active table.")
        return seats

    def analyze(self) -> None:
        """Start a generation-safe background analysis."""
        if self.thread is not None and self.thread.isRunning():
            return
        try:
            state = self._state()
        except Exception as exc:  # noqa: BLE001 - user-facing validation boundary
            self._show_error(str(exc))
            return
        if (
            state.table_state is not None
            and state.table_state.current_actor_seat != state.table_state.hero_seat
        ):
            self._show_error("Action-aware analysis requires Hero to be the current actor.")
            return
        self.analysis_id += 1
        current_id = self.analysis_id
        self.progress.setRange(0, 0)
        self.progress.setFormat("Preparing analysis...")
        self.status_label.setText("Analysis is running. You may cancel or continue editing inputs.")
        self._sync_button_states(running=True)
        # The thread is deliberately parentless. Its deferred deletion must finish before the
        # window can be destroyed, rather than being forced by QObject parent teardown.
        thread = self.qtcore.QThread()
        factory = AnalysisWorker(
            self.qtcore,
            state,
            str(self.range_combo.currentText()),
            _PRESETS[str(self.preset_combo.currentText())],
            7,
            action_aware_preset(str(self.action_preset_combo.currentText())),
        )
        worker = factory.object
        self.thread = thread
        self.worker = worker
        qtcore = self.qtcore
        owner = self

        class _SignalBridge(qtcore.QObject):  # type: ignore[misc, name-defined]
            @qtcore.Slot(int, int)  # type: ignore[untyped-decorator]
            def progress(self, current: int, total: int) -> None:
                owner._progress(current, total, current_id)

            @qtcore.Slot(object)  # type: ignore[untyped-decorator]
            def finished(self, result: object) -> None:
                owner._finished(result, current_id)

            @qtcore.Slot(str)  # type: ignore[untyped-decorator]
            def error(self, message: str) -> None:
                owner._error(message, current_id)

            @qtcore.Slot()  # type: ignore[untyped-decorator]
            def thread_finished(self) -> None:
                owner._thread_finished(thread)

            @qtcore.Slot()  # type: ignore[untyped-decorator]
            def thread_destroyed(self) -> None:
                owner._thread_destroyed(thread)

        bridge = _SignalBridge(self.window)
        self.signal_bridge = bridge
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(bridge.progress)
        worker.finished.connect(bridge.finished)
        worker.error.connect(bridge.error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.error.connect(worker.deleteLater)
        thread.finished.connect(bridge.thread_finished)
        thread.finished.connect(thread.deleteLater)
        thread.destroyed.connect(bridge.thread_destroyed)
        thread.start()

    def cancel(self) -> None:
        """Request prompt cancellation for the active worker."""
        if self.worker is not None:
            self.cancel_button.setEnabled(False)
            self.progress.setFormat("Cancelling...")
            self.status_label.setText(
                "Cancellation requested. Finishing the current evaluation step."
            )
            self.worker.cancel()

    def _progress(self, current: int, total: int, analysis_id: int) -> None:
        if analysis_id != self.analysis_id:
            return
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(current)
        self.progress.setFormat(f"{current:,} / {total:,}")

    def _finished(self, result: object, analysis_id: int) -> None:
        if analysis_id != self.analysis_id or not isinstance(result, AnalysisResult):
            return
        self.latest_result = result
        formatted = _format_result(result, self.settings.percentage_precision)
        if self.training_prompt:
            formatted = self.training_prompt + "\n\n" + formatted
        self.output.setPlainText(formatted)
        self._populate_probability_table(result)
        self._populate_action_table(result)
        action_time = result.action_aware.execution_time if result.action_aware else 0.0
        self.status_label.setText(
            f"Analysis complete: showdown {result.equity.execution_time:.2f}s, "
            f"action-aware {action_time:.2f}s."
        )
        self.tabs.setCurrentWidget(self.output)

    def _error(self, message: str, analysis_id: int) -> None:
        if analysis_id != self.analysis_id:
            return
        friendly = "Analysis cancelled." if "cancel" in message.lower() else message
        self._show_error(friendly)

    def _thread_finished(self, active_thread: Any) -> None:
        if active_thread is self.thread:
            self.progress.setRange(0, 1)
            if self.latest_result is not None:
                self.progress.setValue(1)
                self.progress.setFormat("Complete")
            elif "cancel" in self.output.toPlainText().lower():
                self.progress.setValue(0)
                self.progress.setFormat("Cancelled")
            else:
                self.progress.setValue(0)
                self.progress.setFormat("Ready")
        self._sync_button_states()

    def _thread_destroyed(self, active_thread: Any) -> None:
        """Release Qt references only after deferred QThread destruction completes."""
        if active_thread is not self.thread:
            return
        self.thread = None
        self.worker = None
        if self.signal_bridge is not None:
            self.signal_bridge.deleteLater()
            self.signal_bridge = None
        self._sync_button_states()
        if self.close_pending:
            self.qtcore.QTimer.singleShot(0, self.window.close)
            return
        if self.auto_analysis.isChecked() and self.latest_result is None:
            self._schedule_automatic_analysis()

    def _input_changed(self, *_args: object) -> None:
        if self._suspend_changes:
            return
        self.analysis_id += 1
        self.training_prompt = None
        self.latest_result = None
        self._clear_probability_table()
        self.action_table.setRowCount(0)
        self.output.setPlainText("Inputs changed. Run analysis to refresh the results.")
        self.status_label.setText("Results are out of date.")
        self._update_action_order()
        self._sync_button_states(running=self.thread is not None and self.thread.isRunning())
        if self.auto_analysis.isChecked():
            self._schedule_automatic_analysis()

    def _auto_analysis_changed(self, enabled: bool) -> None:
        self.settings = replace(self.settings, automatic_analysis=enabled)
        self._save_settings_safely()
        if enabled:
            self._schedule_automatic_analysis()
        else:
            self._auto_timer.stop()

    def _schedule_automatic_analysis(self) -> None:
        """Debounce automatic analysis only for a complete, valid Hero decision."""
        self._auto_timer.stop()
        if not self.auto_analysis.isChecked() or self.thread is not None:
            return
        if self._automatic_analysis_state_is_valid():
            self._auto_timer.start()

    def _run_automatic_analysis(self) -> None:
        """Revalidate after the debounce interval before starting work."""
        if self.auto_analysis.isChecked() and self._automatic_analysis_state_is_valid():
            self.analyze()

    def _automatic_analysis_state_is_valid(self) -> bool:
        try:
            state = self._state()
        except Exception:  # noqa: BLE001 - incomplete edits are expected while typing
            return False
        return (
            state.table_state is None
            or state.table_state.current_actor_seat == state.table_state.hero_seat
        )

    def _player_count_changed(self, player_count: int) -> None:
        self.players_behind.setMaximum(max(0, player_count - 1))
        self.aggressor_seat.setMaximum(max(0, player_count - 1))
        self.current_actor_seat.setMaximum(max(0, player_count - 1))
        self.player_overrides = {
            seat: values for seat, values in self.player_overrides.items() if seat < player_count
        }
        self._update_action_order()

    def _update_action_order(self) -> None:
        if not hasattr(self, "action_order_label"):
            return
        board_count = sum(1 for edit in self.card_edits[2:] if edit.text().strip())
        street = {0: "preflop", 3: "flop", 4: "turn", 5: "river"}.get(board_count, "flop")
        try:
            table = self._build_table_state(street)
            order = " -> ".join(
                table.player(seat).position.replace("_", " ").title()
                for seat in table.action_order(table.current_actor_seat)
            )
            behind = table.players_after_hero()
            behind_text = ", ".join(player.position.replace("_", " ").title() for player in behind)
            self.action_order_label.setText(
                f"Action order: {order}. Behind hero: {behind_text or 'none'}."
            )
        except Exception as exc:  # noqa: BLE001 - live preview validation boundary
            self.action_order_label.setText(f"Action order unavailable: {exc}")

    def opponent_editor(self) -> None:
        """Edit individual opponent status, stack, profile, range, and prior action."""
        board_count = sum(1 for edit in self.card_edits[2:] if edit.text().strip())
        street = {0: "preflop", 3: "flop", 4: "turn", 5: "river"}.get(board_count, "flop")
        try:
            table_state = self._build_table_state(street)
        except Exception as exc:  # noqa: BLE001 - user-facing validation boundary
            self._show_error(str(exc))
            return
        dialog = self.qtwidgets.QDialog(self.window)
        dialog.setWindowTitle("Advanced opponent editor")
        layout = self.qtwidgets.QVBoxLayout(dialog)
        editor = self.qtwidgets.QTableWidget(len(table_state.players), 8)
        editor.setHorizontalHeaderLabels(
            ["Seat", "Position", "Folded", "All-in", "Stack", "Profile", "Range", "Previous"]
        )
        controls: dict[int, tuple[Any, Any, Any, Any, Any, Any, Any]] = {}
        for row, player in enumerate(table_state.players):
            seat_item = self.qtwidgets.QTableWidgetItem(str(player.seat))
            seat_item.setFlags(seat_item.flags() & ~self.qtcore.Qt.ItemFlag.ItemIsEditable)
            editor.setItem(row, 0, seat_item)
            position_item = self.qtwidgets.QTableWidgetItem(player.position)
            editor.setItem(row, 1, position_item)
            folded = self.qtwidgets.QCheckBox()
            folded.setChecked(player.folded)
            all_in = self.qtwidgets.QCheckBox()
            all_in.setChecked(player.all_in)
            stack = self._money_spin(player.stack)
            profile = self.qtwidgets.QComboBox()
            for option in OpponentProfile:
                profile.addItem(option.display_name, option.value)
            profile.setCurrentIndex(profile.findData(player.profile.value))
            range_edit = self.qtwidgets.QLineEdit(player.range_text)
            previous = self.qtwidgets.QLineEdit(", ".join(player.previous_actions))
            if player.is_hero:
                folded.setEnabled(False)
                all_in.setEnabled(False)
                profile.setEnabled(False)
                range_edit.setEnabled(False)
            editor.setCellWidget(row, 2, folded)
            editor.setCellWidget(row, 3, all_in)
            editor.setCellWidget(row, 4, stack)
            editor.setCellWidget(row, 5, profile)
            editor.setCellWidget(row, 6, range_edit)
            editor.setCellWidget(row, 7, previous)
            controls[player.seat] = (
                position_item,
                folded,
                all_in,
                stack,
                profile,
                range_edit,
                previous,
            )
        editor.horizontalHeader().setSectionResizeMode(
            self.qtwidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        editor.horizontalHeader().setSectionResizeMode(
            1, self.qtwidgets.QHeaderView.ResizeMode.Stretch
        )
        editor.horizontalHeader().setSectionResizeMode(
            7, self.qtwidgets.QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(editor)
        buttons = self.qtwidgets.QDialogButtonBox(
            self.qtwidgets.QDialogButtonBox.StandardButton.Save
            | self.qtwidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.resize(980, 420)
        if dialog.exec() != self.qtwidgets.QDialog.DialogCode.Accepted:
            return
        overrides: dict[int, TablePlayer] = {}
        for player in table_state.players:
            if player.is_hero:
                continue
            position_item, folded, all_in, stack, profile, range_edit, previous = controls[
                player.seat
            ]
            is_folded = folded.isChecked()
            is_all_in = all_in.isChecked() and not is_folded
            actions = tuple(
                action.strip() for action in previous.text().split(",") if action.strip()
            )
            overrides[player.seat] = replace(
                player,
                position=position_item.text().strip() or player.position,
                folded=is_folded,
                all_in=is_all_in,
                stack=0.0 if is_all_in else float(stack.value()),
                profile=OpponentProfile(str(profile.currentData())),
                range_text=range_edit.text().strip() or "random",
                previous_actions=actions,
                eligible_to_act=not is_folded and not is_all_in,
                acted_this_round=bool(actions),
            )
        self.player_overrides = overrides
        self._input_changed()

    def _pick_card(self, field: Any) -> None:
        dialog = self.qtwidgets.QDialog(self.window)
        dialog.setWindowTitle("Select card")
        grid = self.qtwidgets.QGridLayout(dialog)
        used: set[Card] = set()
        for edit in self.card_edits:
            if edit is field or not edit.text().strip():
                continue
            try:
                used.add(Card.from_code(edit.text()))
            except Exception:  # noqa: BLE001 - invalid manual input is handled on analyze
                continue
        for row, rank in enumerate(reversed(tuple(Rank))):
            for col, suit in enumerate(Suit):
                card = Card(rank, suit)
                button = self.qtwidgets.QPushButton(card.short_code)
                button.setAccessibleName(card.display_name)
                button.setToolTip(card.display_name if card not in used else "Already used")
                button.setEnabled(card not in used)
                button.clicked.connect(
                    lambda _checked=False, selected=card: self._set_card(dialog, field, selected)
                )
                grid.addWidget(button, row, col)
        dialog.exec()

    def _set_card(self, dialog: Any, field: Any, card: Card) -> None:
        field.setText(card.code)
        dialog.accept()

    def clear_current_street(self) -> None:
        board = self.card_edits[2:]
        if board[4].text().strip():
            board[4].clear()
        elif board[3].text().strip():
            board[3].clear()
            board[4].clear()
        elif any(edit.text().strip() for edit in board[:3]):
            for edit in board:
                edit.clear()
        else:
            self.status_label.setText("No community-card street is entered.")

    def new_hand(self) -> None:
        self.cancel()
        self._suspend_changes = True
        for edit in self.card_edits:
            edit.clear()
        self._suspend_changes = False
        self.analysis_id += 1
        self.training_prompt = None
        self.latest_result = None
        self.output.setPlainText(_EMPTY_RESULT)
        self._clear_probability_table()
        self.action_table.setRowCount(0)
        self.status_label.setText("New hand ready.")
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setFormat("Ready")
        self._sync_button_states(running=self.thread is not None and self.thread.isRunning())

    def save(self) -> None:
        try:
            state = self._state()
        except Exception as exc:  # noqa: BLE001 - user-facing validation boundary
            self._show_error(str(exc))
            return
        default_path = user_data_dir() / "hands" / "hand.json"
        path_text, _selected_filter = self.qtwidgets.QFileDialog.getSaveFileName(
            self.window, "Save hand", str(default_path), "JSON Files (*.json)"
        )
        if not path_text:
            return
        try:
            summary = self.output.toPlainText() if self.latest_result else None
            path = save_hand(
                SavedHand(state, str(self.range_combo.currentText()), "", summary),
                Path(path_text),
            )
        except Exception as exc:  # noqa: BLE001 - file-system boundary
            self._show_error(f"The hand could not be saved. {exc}")
            return
        self.status_label.setText(f"Hand saved to {path}.")

    def load(self) -> None:
        default_dir = user_data_dir() / "hands"
        path_text, _selected_filter = self.qtwidgets.QFileDialog.getOpenFileName(
            self.window, "Load hand", str(default_dir), "JSON Files (*.json)"
        )
        if not path_text:
            return
        try:
            hand = load_hand(Path(path_text))
        except Exception as exc:  # noqa: BLE001 - file-system and validation boundary
            self._show_error(f"The hand could not be loaded. {exc}")
            return
        self._apply_state(hand.game_state)
        self.range_combo.setCurrentText(hand.opponent_range)
        self.status_label.setText(
            f"Loaded {Path(path_text).name}. Run analysis to refresh results."
        )

    def export(self) -> None:
        if self.latest_result is None:
            self._show_error("Run analysis before exporting.")
            return
        default_path = user_data_dir() / "exports" / "analysis.md"
        path_text, _selected_filter = self.qtwidgets.QFileDialog.getSaveFileName(
            self.window, "Export analysis", str(default_path), "Markdown (*.md);;JSON (*.json)"
        )
        if not path_text:
            return
        path = Path(path_text)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.suffix.lower() == ".json":
                export_analysis_json(self.latest_result, path)
            else:
                export_analysis_markdown(self.latest_result, path)
        except Exception as exc:  # noqa: BLE001 - file-system boundary
            self._show_error(f"The analysis could not be exported. {exc}")
            return
        self.status_label.setText(f"Analysis exported to {path}.")

    def settings_dialog(self) -> None:
        dialog = self.qtwidgets.QDialog(self.window)
        dialog.setWindowTitle("Peaceful Poker settings")
        layout = self.qtwidgets.QFormLayout(dialog)
        theme = self.qtwidgets.QComboBox()
        theme.addItems(["light", "dark"])
        theme.setCurrentText(self.settings.theme)
        players = self.qtwidgets.QSpinBox()
        players.setRange(2, 10)
        players.setValue(self.settings.default_player_count)
        simulations = self.qtwidgets.QComboBox()
        for name, count in _PRESETS.items():
            simulations.addItem(f"{name} ({count:,})", count)
        simulations.setCurrentIndex(
            max(0, simulations.findData(self.settings.default_simulation_count))
        )
        precision = self.qtwidgets.QSpinBox()
        precision.setRange(0, 4)
        precision.setValue(self.settings.percentage_precision)
        detailed = self.qtwidgets.QCheckBox("Show detailed explanations")
        detailed.setChecked(self.settings.detailed_explanations)
        automatic = self.qtwidgets.QCheckBox("Analyze automatically")
        automatic.setChecked(self.auto_analysis.isChecked())
        layout.addRow("Theme", theme)
        layout.addRow("Default players", players)
        layout.addRow("Default simulations", simulations)
        layout.addRow("Percentage decimals", precision)
        layout.addRow("Explanations", detailed)
        layout.addRow("Automation", automatic)
        buttons = self.qtwidgets.QDialogButtonBox(
            self.qtwidgets.QDialogButtonBox.StandardButton.Save
            | self.qtwidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        if dialog.exec() != self.qtwidgets.QDialog.DialogCode.Accepted:
            return
        self.settings = replace(
            self.settings,
            theme=str(theme.currentText()),
            default_player_count=int(players.value()),
            default_simulation_count=int(simulations.currentData()),
            percentage_precision=int(precision.value()),
            detailed_explanations=detailed.isChecked(),
            automatic_analysis=automatic.isChecked(),
        )
        self.auto_analysis.setChecked(self.settings.automatic_analysis)
        self._apply_theme(self.settings.theme)
        self._save_settings_safely()
        if self.latest_result is not None:
            self.output.setPlainText(
                _format_result(self.latest_result, self.settings.percentage_precision)
            )
            self._populate_probability_table(self.latest_result)
        self.status_label.setText("Settings saved.")

    def training(self) -> None:
        if self.thread is not None and self.thread.isRunning():
            self._show_error("Cancel the current analysis before loading a training scenario.")
            return
        state = generate_training_state(TrainingDifficulty.BEGINNER, seed=11)
        self._apply_state(state)
        self._suspend_changes = True
        self.preset_combo.setCurrentText("Quick")
        self._suspend_changes = False
        choices = ", ".join(action.display_name for action in legal_actions(state))
        self.training_prompt = (
            "Training prompt: choose an action before reading the completed analysis.\n"
            f"Legal choices: {choices}"
        )
        self.output.setPlainText(self.training_prompt)
        self.status_label.setText("Training scenario loaded; analysis is starting.")
        self.analyze()

    def about(self) -> None:
        box = self.qtwidgets.QMessageBox(self.window)
        box.setWindowTitle("About Peaceful Poker")
        box.setText("Peaceful Poker 1.1.0")
        box.setInformativeText(
            "An educational No-Limit Texas Hold'em decision trainer. Raw showdown equity and "
            "action-aware EV depend on entered ranges and behavior profiles; neither is GTO or "
            "guaranteed profitable.\n\nSaved data: " + str(user_data_dir())
        )
        if self.qtgui is not None:
            icon_path = resource_path("peaceful_poker.ico")
            if icon_path.exists():
                box.setWindowIcon(self.qtgui.QIcon(str(icon_path)))
        box.exec()

    def _apply_state(self, state: GameState) -> None:
        self._suspend_changes = True
        self.training_prompt = None
        self.players.setValue(state.active_players)
        self.position.setCurrentText(state.hero_position.display_name)
        self.small_blind.setValue(state.small_blind)
        self.big_blind.setValue(state.big_blind)
        self.ante.setValue(state.ante)
        self.pot.setValue(state.pot_size)
        self.call.setValue(state.amount_to_call)
        self.stack.setValue(state.hero_stack)
        self.effective.setValue(state.effective_stack)
        if state.table_state is not None:
            self.current_actor_seat.setValue(
                -1
                if state.table_state.current_actor_seat == state.table_state.hero_seat
                else state.table_state.current_actor_seat
            )
            opponents = state.table_state.active_opponents
            if opponents:
                self.profile_combo.setCurrentIndex(
                    self.profile_combo.findData(opponents[0].profile.value)
                )
                self.range_combo.setCurrentText(opponents[0].range_text)
            self.folded_seats.setText(
                ", ".join(str(player.seat) for player in state.table_state.players if player.folded)
            )
            self.called_seats.setText(
                ", ".join(
                    str(player.seat)
                    for player in state.table_state.players
                    if any("call" in action.lower() for action in player.previous_actions)
                )
            )
            aggressors = [
                player.seat
                for player in state.table_state.players
                if any(
                    "bet" in action.lower() or "raise" in action.lower()
                    for action in player.previous_actions
                )
            ]
            self.aggressor_seat.setValue(aggressors[-1] if aggressors else -1)
            self.players_behind.setValue(len(state.table_state.players_after_hero()))
            self.player_overrides = {
                player.seat: player for player in state.table_state.players if not player.is_hero
            }
        values = [*state.hero_cards, *state.community_cards]
        for index, edit in enumerate(self.card_edits):
            edit.setText(values[index].code if index < len(values) else "")
        self._suspend_changes = False
        self.analysis_id += 1
        self.latest_result = None
        self.output.setPlainText("Hand loaded. Run analysis to calculate current results.")
        self._clear_probability_table()
        self.action_table.setRowCount(0)
        self._update_action_order()
        self._sync_button_states()

    def _apply_theme(self, theme: str) -> None:
        selected = theme if theme in {"light", "dark"} else "light"
        path = resource_path(f"{selected}.qss")
        try:
            stylesheet = path.read_text(encoding="utf-8")
        except OSError:
            stylesheet = ""
        self.window.setStyleSheet(stylesheet)

    def _populate_probability_table(self, result: AnalysisResult) -> None:
        precision = self.settings.percentage_precision
        probabilities = result.final_hand_probabilities
        for row, category in enumerate(HandCategory):
            values = (
                category.display_name,
                _percent(probabilities.exact_category_probabilities[category], precision),
                _percent(probabilities.at_least_category_probabilities[category], precision),
            )
            for column, value in enumerate(values):
                self.probability_table.setItem(row, column, self.qtwidgets.QTableWidgetItem(value))

    def _populate_action_table(self, result: AnalysisResult) -> None:
        action_aware = result.action_aware
        if action_aware is None:
            self.action_table.setRowCount(0)
            return
        precision = self.settings.percentage_precision
        self.action_table.setRowCount(len(action_aware.action_results))
        for row, action_result in enumerate(action_aware.action_results):
            values = (
                action_result.candidate.label,
                f"{action_result.estimated_net_ev:.2f}",
                f"{action_result.confidence_interval_low:.2f} to "
                f"{action_result.confidence_interval_high:.2f}",
                _percent(action_result.immediate_fold_probability, precision),
                _percent(action_result.exactly_one_continues_probability, precision),
                _percent(action_result.multiple_continue_probability, precision),
                _percent(action_result.facing_raise_probability, precision),
                _percent(action_result.conditional_showdown_equity, precision),
            )
            for column, value in enumerate(values):
                self.action_table.setItem(row, column, self.qtwidgets.QTableWidgetItem(value))

    def _clear_probability_table(self) -> None:
        for row, category in enumerate(HandCategory):
            self.probability_table.setItem(
                row, 0, self.qtwidgets.QTableWidgetItem(category.display_name)
            )
            self.probability_table.setItem(row, 1, self.qtwidgets.QTableWidgetItem("Unavailable"))
            self.probability_table.setItem(row, 2, self.qtwidgets.QTableWidgetItem("Unavailable"))

    def _sync_button_states(self, running: bool | None = None) -> None:
        is_running = (
            running if running is not None else self.thread is not None and self.thread.isRunning()
        )
        self.analyze_button.setEnabled(not is_running)
        self.cancel_button.setEnabled(is_running)
        self.training_button.setEnabled(not is_running)
        self.export_button.setEnabled(self.latest_result is not None and not is_running)

    def _show_error(self, message: str) -> None:
        self.latest_result = None
        self.output.setPlainText(message)
        self.status_label.setText("Unable to complete the requested action.")
        self._clear_probability_table()
        self.action_table.setRowCount(0)
        self._sync_button_states(running=self.thread is not None and self.thread.isRunning())

    def _save_settings_safely(self) -> None:
        try:
            save_settings(self.settings)
        except Exception as exc:  # noqa: BLE001 - closing/settings file-system boundary
            self.status_label.setText(f"Settings could not be saved. {exc}")

    def _restore_geometry(self) -> None:
        if not self.settings.window_geometry:
            return
        try:
            encoded = self.settings.window_geometry.encode("ascii")
            self.window.restoreGeometry(self.qtcore.QByteArray.fromBase64(encoded))
        except Exception:  # noqa: BLE001 - invalid geometry should never prevent startup
            self.startup_warning = "Saved window geometry was invalid and has been reset."

    def _close_event(self, event: Any) -> None:
        if self.thread is not None:
            if self.thread.isRunning():
                if self.worker is not None:
                    self.worker.cancel()
                self.thread.requestInterruption()
                self.thread.quit()
            self.close_pending = True
            self.status_label.setText("Cancelling analysis before closing...")
            event.ignore()
            return
        geometry = bytes(self.window.saveGeometry().toBase64()).decode("ascii")
        self.settings = replace(self.settings, window_geometry=geometry)
        self._save_settings_safely()
        event.accept()


def _format_result(result: AnalysisResult, precision: int = 1) -> str:
    best_five = " ".join(card.code for card in result.current_hand.best_five_cards) or "Preflop"
    draws = ", ".join(draw.description for draw in result.draws) or "None detected"
    pot_odds = result.pot_odds
    ev = (
        "Unavailable"
        if pot_odds.simplified_call_ev is None
        else f"{pot_odds.simplified_call_ev:.2f} chips"
    )
    lines = [
        f"Street: {result.game_state.street.display_name}",
        f"Current hand: {result.current_hand.description}",
        f"Best five: {best_five}",
        f"Hero cards used: {result.current_hand.hero_cards_used}",
        f"Board texture: {result.board_analysis.overall_texture.value.replace('_', ' ').title()}",
        f"Draws: {draws}",
        f"Apparent unique outs: {len(result.outs.unique_outs)}",
        "",
        "RAW SHOWDOWN ANALYSIS",
        "Assumption: every currently included opponent reaches showdown.",
        f"Win: {_percent(result.equity.win_percentage, precision)}",
        f"Tie: {_percent(result.equity.tie_percentage, precision)}",
        f"Loss: {_percent(result.equity.loss_percentage, precision)}",
        f"Total equity: {_percent(result.equity.total_equity, precision)}",
        f"Calculation: {result.equity.calculation_method.replace('_', ' ')} "
        f"({result.equity.iterations:,} outcomes)",
        "Improvement probability: "
        + _percent(result.final_hand_probabilities.improvement_probability, precision),
        "",
        f"Current pot: {pot_odds.current_pot:.2f} chips",
        f"Amount to call: {pot_odds.amount_to_call:.2f} chips",
        f"Required equity: {_percent(pot_odds.required_equity, precision)}",
        f"Simplified call EV: {ev}",
        f"Legal actions: {', '.join(result.recommendation.legal_alternatives)}",
        f"Showdown-only rule recommendation: {result.recommendation.primary_action} "
        f"({result.recommendation.confidence.value} confidence)",
        "Reasons: " + "; ".join(result.recommendation.reasons),
        "Risks: " + "; ".join(result.recommendation.risks),
        "Assumptions: " + "; ".join(result.recommendation.assumptions),
        result.recommendation.explanation,
    ]
    if result.action_aware is not None:
        action_aware = result.action_aware
        lines.extend(
            [
                "",
                "ACTION-AWARE ANALYSIS",
                "Action-aware results depend on the entered opponent profiles and are estimates, "
                "not exact predictions.",
                f"Recommended action by estimated net EV: {action_aware.recommended_action}",
            ]
        )
        if action_aware.uncertainty_note:
            lines.append("Uncertainty: " + action_aware.uncertainty_note)
        for action_result in action_aware.action_results:
            lines.append(
                f"{action_result.candidate.label}: EV {action_result.estimated_net_ev:.2f} chips; "
                f"95% CI {action_result.confidence_interval_low:.2f} to "
                f"{action_result.confidence_interval_high:.2f}; all fold "
                f"{_percent(action_result.immediate_fold_probability, precision)}; "
                f"continue {_percent(action_result.continue_probability, precision)}; "
                f"faces raise {_percent(action_result.facing_raise_probability, precision)}; "
                f"called equity "
                f"{_percent(action_result.conditional_showdown_equity, precision)}"
            )
        lines.append("Action-aware assumptions: " + "; ".join(action_aware.assumptions))
    return "\n".join(lines)


def _percent(value: float, precision: int) -> str:
    return f"{value * 100:.{precision}f}%"
