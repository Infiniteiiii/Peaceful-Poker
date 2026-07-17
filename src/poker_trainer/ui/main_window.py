"""Main Peaceful Poker desktop window."""

from dataclasses import replace
from functools import partial
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
_PREVIOUS_ACTION_OPTIONS = ("None", "Checked", "Called", "Bet", "Raised")
_PRESETS = {
    "Quick": SimulationPreset.QUICK,
    "Standard": SimulationPreset.STANDARD,
    "Accurate": SimulationPreset.ACCURATE,
    "Very Accurate": SimulationPreset.VERY_ACCURATE,
}
_ACTION_PRESETS = ("Quick", "Standard", "Accurate")
_EMPTY_RESULT = "Enter two hero cards and a valid board, then choose Analyze."
_SUIT_SYMBOLS = {
    Suit.SPADES: "♠",
    Suit.HEARTS: "♥",
    Suit.DIAMONDS: "♦",
    Suit.CLUBS: "♣",
}
_SYMBOL_TO_SUIT_CODE = {symbol: suit.code for suit, symbol in _SUIT_SYMBOLS.items()}

_THEME_TOKENS = {
    "dark": {
        "bg_app": "#0E1117",
        "bg_surface": "#161B22",
        "bg_surface_raised": "#1C2128",
        "border_subtle": "#2A3441",
        "border_focus": "#4F8CFF",
        "accent_primary": "#4F8CFF",
        "accent_hover": "#6CA3FF",
        "accent_secondary": "#58A6FF",
        "accent_warning": "#F5A623",
        "accent_negative": "#FF5C6C",
        "text_primary": "#F5F7FA",
        "text_secondary": "#9AA5B1",
        "text_disabled": "#6E7681",
    },
    "light": {
        "bg_app": "#F2F3F5",
        "bg_surface": "#F8F9FA",
        "bg_surface_raised": "#EDEEF1",
        "border_subtle": "#CDD2D8",
        "border_focus": "#4A7FE5",
        "accent_primary": "#4A7FE5",
        "accent_hover": "#5E90EE",
        "accent_secondary": "#5E90EE",
        "accent_warning": "#D4891A",
        "accent_negative": "#D94F5C",
        "text_primary": "#1A2030",
        "text_secondary": "#5A6370",
        "text_disabled": "#9AA0A8",
    },
}


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
        icon_path = resource_path("Logo.png")
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

    def reload_ui(self) -> None:
        """Reload UI stylesheet and theme (for hot-reload development)."""
        try:
            self._apply_theme(self.settings.theme)
            print("[HOT RELOAD] UI reloaded successfully")
        except Exception as e:
            print(f"[HOT RELOAD] Error reloading: {e}")

    def _build(self) -> None:
        central = self.qtwidgets.QWidget()
        root = self.qtwidgets.QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(12)
        root.addLayout(self._build_header())

        self._landing_page = self._build_landing_page()
        self._main_area = self._build_main_area()

        root.addWidget(self._landing_page)
        root.addWidget(self._main_area)
        self._main_area.hide()

        self.window.setCentralWidget(central)

    def _build_header(self) -> Any:
        bar = self.qtwidgets.QHBoxLayout()
        bar.setSpacing(12)

        title = self.qtwidgets.QLabel("Peaceful Poker")
        title.setObjectName("appTitle")
        left = self.qtcore.Qt.AlignmentFlag.AlignLeft
        vcenter = self.qtcore.Qt.AlignmentFlag.AlignVCenter
        title.setAlignment(left | vcenter)
        bar.addWidget(title)

        self.home_button = self.qtwidgets.QPushButton("\u2190 Back")
        self.home_button.setObjectName("headerBack")
        self.home_button.setToolTip("Return to the welcome screen")
        self.home_button.setCursor(self.qtcore.Qt.CursorShape.PointingHandCursor)
        self.home_button.clicked.connect(self._show_landing)
        self.home_button.hide()
        bar.addWidget(self.home_button)

        bar.addStretch(1)

        self.theme_toggle = self.qtwidgets.QToolButton()
        self.theme_toggle.setCheckable(True)
        self.theme_toggle.setChecked(self.settings.theme == "dark")
        self.theme_toggle.setText("Dark" if self.settings.theme == "dark" else "Light")
        self.theme_toggle.setObjectName("themeToggle")
        self.theme_toggle.clicked.connect(self._toggle_theme)
        self.theme_toggle.setToolTip("Toggle between light and dark theme.")
        bar.addWidget(self.theme_toggle)

        return bar

    def _build_landing_page(self) -> Any:
        """Poker-themed landing page with hero section and feature cards."""
        page = self.qtwidgets.QWidget()
        page.setObjectName("landingPage")
        outer = self.qtwidgets.QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Hero
        hero = self.qtwidgets.QWidget()
        hero.setObjectName("landingHero")
        hero_layout = self.qtwidgets.QVBoxLayout(hero)
        hero_layout.setContentsMargins(48, 60, 48, 52)
        hero_layout.setSpacing(0)
        hero_layout.addStretch(1)

        suits = self.qtwidgets.QLabel("\u2660  \u2665  \u2666  \u2663")
        suits.setObjectName("landingSuits")
        suits.setAlignment(self.qtcore.Qt.AlignmentFlag.AlignCenter)
        hero_layout.addWidget(suits)
        hero_layout.addSpacing(16)

        title = self.qtwidgets.QLabel("Peaceful Poker")
        title.setObjectName("landingTitle")
        title.setAlignment(self.qtcore.Qt.AlignmentFlag.AlignCenter)
        hero_layout.addWidget(title)
        hero_layout.addSpacing(12)

        subtitle = self.qtwidgets.QLabel(
            "Your personal No-Limit Hold\u2019em trainer and equity analyzer."
        )
        subtitle.setObjectName("landingSubtitle")
        subtitle.setAlignment(self.qtcore.Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        hero_layout.addWidget(subtitle)
        hero_layout.addSpacing(36)

        enter = self.qtwidgets.QPushButton("Get Started  \u2192")
        enter.setObjectName("landingEnter")
        enter.setToolTip("Open the main application")
        enter.setFixedWidth(220)
        enter.setFixedHeight(52)
        enter.setCursor(self.qtcore.Qt.CursorShape.PointingHandCursor)
        enter.clicked.connect(self._show_main_area)
        hero_layout.addWidget(enter, 0, self.qtcore.Qt.AlignmentFlag.AlignHCenter)
        hero_layout.addStretch(1)
        outer.addWidget(hero, 2)

        # Divider
        div = self.qtwidgets.QFrame()
        div.setObjectName("landingDivider")
        div.setFixedHeight(1)
        outer.addWidget(div)

        # Feature strip
        feat_widget = self.qtwidgets.QWidget()
        feat_widget.setObjectName("landingFeatures")
        feat_layout = self.qtwidgets.QHBoxLayout(feat_widget)
        feat_layout.setContentsMargins(48, 28, 48, 36)
        feat_layout.setSpacing(20)

        for icon, feat_title, feat_body in [
            (
                "\U0001f4ca",
                "Equity Analysis",
                "Monte Carlo simulation across any number of players.",
            ),
            (
                "\U0001f9e0",
                "Action-Aware EV",
                "Model opponent fold/call/raise frequencies for real EV.",
            ),
            (
                "\U0001f3af",
                "Training Mode",
                "Practice decisions on generated scenarios with feedback.",
            ),
        ]:
            card = self.qtwidgets.QFrame()
            card.setObjectName("featureCard")
            cl = self.qtwidgets.QVBoxLayout(card)
            cl.setContentsMargins(20, 20, 20, 20)
            cl.setSpacing(8)
            il = self.qtwidgets.QLabel(icon)
            il.setObjectName("featureIcon")
            il.setAlignment(self.qtcore.Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(il)
            tl = self.qtwidgets.QLabel(feat_title)
            tl.setObjectName("featureTitle")
            tl.setAlignment(self.qtcore.Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(tl)
            bl = self.qtwidgets.QLabel(feat_body)
            bl.setObjectName("featureBody")
            bl.setAlignment(self.qtcore.Qt.AlignmentFlag.AlignCenter)
            bl.setWordWrap(True)
            cl.addWidget(bl)
            feat_layout.addWidget(card)

        outer.addWidget(feat_widget, 1)
        return page

    def _build_main_area(self) -> Any:
        """Construct the primary application area (no sidebar)."""
        container = self.qtwidgets.QWidget()
        layout = self.qtwidgets.QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        self.sidebar_widget = None
        layout.addLayout(self._button_grid())
        self.main_splitter = self.qtwidgets.QSplitter(self.qtcore.Qt.Orientation.Horizontal)
        self.main_splitter.setObjectName("mainSplitter")
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(10)
        self.main_splitter.addWidget(self._setup_panel())
        self.main_splitter.addWidget(self._results_panel())
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([580, 580])
        layout.addWidget(self.main_splitter, 1)
        return container

    def _build_sidebar(self) -> Any:  # kept for API compatibility
        return self.qtwidgets.QFrame()

    def _toggle_theme(self) -> None:
        from contextlib import suppress

        new_theme = "dark" if self.theme_toggle.isChecked() else "light"
        self.settings = replace(self.settings, theme=new_theme)
        self.theme_toggle.setText("Dark" if self.settings.theme == "dark" else "Light")
        self._apply_theme(self.settings.theme)
        with suppress(Exception):
            save_settings(self.settings)

    def _setup_panel(self) -> Any:
        content = self.qtwidgets.QWidget()
        outer = self.qtwidgets.QVBoxLayout(content)
        outer.setSpacing(16)
        outer.setContentsMargins(0, 0, 0, 0)

        label_width = 170

        def _add_section_title(text: str) -> None:
            title_label = self.qtwidgets.QLabel(text)
            title_label.setObjectName("sectionTitle")
            outer.addWidget(title_label)

        def _configure_form_layout(layout: Any) -> None:
            layout.setLabelAlignment(
                self.qtcore.Qt.AlignmentFlag.AlignLeft | self.qtcore.Qt.AlignmentFlag.AlignVCenter
            )
            layout.setFormAlignment(
                self.qtcore.Qt.AlignmentFlag.AlignLeft | self.qtcore.Qt.AlignmentFlag.AlignTop
            )
            layout.setFieldGrowthPolicy(
                self.qtwidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
            )
            layout.setHorizontalSpacing(22)
            layout.setVerticalSpacing(12)

        def _add_form_row(layout: Any, label_text: str, field: Any) -> None:
            label = self.qtwidgets.QLabel(label_text)
            label.setObjectName("fieldLabel")
            label.setMinimumWidth(label_width)
            label.setAlignment(
                self.qtcore.Qt.AlignmentFlag.AlignLeft | self.qtcore.Qt.AlignmentFlag.AlignVCenter
            )
            layout.addRow(label, field)

        self.players = self._spinbox_styled(
            self.settings.default_player_count, min_val=2, max_val=10
        )
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
        self.players_behind = self._spinbox_styled(
            0, min_val=0, max_val=max(0, self.settings.default_player_count - 1)
        )
        self.folded_seats = self.qtwidgets.QLineEdit()
        self.folded_seats.setPlaceholderText("e.g. 2, 4")
        self.called_seats = self.qtwidgets.QLineEdit()
        self.called_seats.setPlaceholderText("e.g. 1, 3")
        self.aggressor_seat = self._spinbox_styled(0, min_val=-1, max_val=9)
        self.aggressor_seat.setSpecialValueText("None")
        self.current_actor_seat = self._spinbox_styled(-1, min_val=-1, max_val=9)
        self.current_actor_seat.setSpecialValueText("Hero")
        self.action_order_label = self.qtwidgets.QLabel("Action order: calculating...")
        self.action_order_label.setWordWrap(True)
        self.advanced_opponents = self.qtwidgets.QPushButton("Edit individual opponents")
        self.auto_analysis = self.qtwidgets.QCheckBox("Analyze automatically after changes")
        self.auto_analysis.setChecked(self.settings.automatic_analysis)

        _add_section_title("Table")
        table_group = self.qtwidgets.QGroupBox()
        table_group.setObjectName("settingsCard")
        table_layout = self.qtwidgets.QFormLayout(table_group)
        _configure_form_layout(table_layout)
        _add_form_row(table_layout, "Active Players", self.players)
        _add_form_row(table_layout, "Hero Position", self.position)
        _add_form_row(table_layout, "Small Blind", self.small_blind)
        _add_form_row(table_layout, "Big Blind", self.big_blind)
        _add_form_row(table_layout, "Ante", self.ante)
        table_helper = self.qtwidgets.QLabel(
            "Seats, position, and blind structure for the current hand."
        )
        table_helper.setObjectName("groupHelper")
        table_helper.setWordWrap(True)
        table_layout.addRow(table_helper)
        outer.addWidget(table_group)

        _add_section_title("Money")
        money_group = self.qtwidgets.QGroupBox()
        money_group.setObjectName("settingsCard")
        money_layout = self.qtwidgets.QFormLayout(money_group)
        _configure_form_layout(money_layout)
        _add_form_row(money_layout, "Current Pot", self.pot)
        _add_form_row(money_layout, "Amount to Call", self.call)
        _add_form_row(money_layout, "Hero Stack", self.stack)
        _add_form_row(money_layout, "Effective Stack", self.effective)
        money_helper = self.qtwidgets.QLabel(
            "Chips and effective investment for the current decision."
        )
        money_helper.setObjectName("groupHelper")
        money_helper.setWordWrap(True)
        money_layout.addRow(money_helper)
        outer.addWidget(money_group)

        _add_section_title("Action So Far")
        action_group = self.qtwidgets.QGroupBox()
        action_group.setObjectName("settingsCard")
        action_layout = self.qtwidgets.QFormLayout(action_group)
        _configure_form_layout(action_layout)
        _add_form_row(action_layout, "Previous Action", self.previous_action)
        _add_form_row(action_layout, "Bettor / Raiser Seat", self.aggressor_seat)
        _add_form_row(action_layout, "Current Actor Seat", self.current_actor_seat)
        _add_form_row(action_layout, "Folded Seat Numbers", self.folded_seats)
        _add_form_row(action_layout, "Called Seat Numbers", self.called_seats)
        _add_form_row(action_layout, "Players Behind Hero", self.players_behind)
        action_helper = self.qtwidgets.QLabel("Opponent activity and action order before hero.")
        action_helper.setObjectName("groupHelper")
        action_helper.setWordWrap(True)
        action_layout.addRow(action_helper)
        outer.addWidget(action_group)

        _add_section_title("Opponent Model")
        opponent_group = self.qtwidgets.QGroupBox()
        opponent_group.setObjectName("settingsCard")
        opponent_layout = self.qtwidgets.QFormLayout(opponent_group)
        _configure_form_layout(opponent_layout)
        _add_form_row(opponent_layout, "Opponent Range", self.range_combo)
        _add_form_row(opponent_layout, "Opponent Profile", self.profile_combo)
        opponent_helper = self.qtwidgets.QLabel(
            "Assumptions that shape opponent behavior in the analysis."
        )
        opponent_helper.setObjectName("groupHelper")
        opponent_helper.setWordWrap(True)
        opponent_layout.addRow(opponent_helper)
        outer.addWidget(opponent_group)

        _add_section_title("Analysis Settings")
        analysis_group = self.qtwidgets.QGroupBox()
        analysis_group.setObjectName("settingsCard")
        analysis_layout = self.qtwidgets.QFormLayout(analysis_group)
        _configure_form_layout(analysis_layout)
        _add_form_row(analysis_layout, "Simulation Accuracy", self.preset_combo)
        _add_form_row(analysis_layout, "Action-Aware Accuracy", self.action_preset_combo)
        _add_form_row(analysis_layout, "Analysis Mode", self.auto_analysis)
        analysis_helper = self.qtwidgets.QLabel(
            "Controls how the analysis is computed and refreshed."
        )
        analysis_helper.setObjectName("groupHelper")
        analysis_helper.setWordWrap(True)
        analysis_layout.addRow(analysis_helper)
        outer.addWidget(analysis_group)

        self.advanced_opponents = self.qtwidgets.QPushButton("Edit individual opponents")
        self.action_order_label = self.qtwidgets.QLabel("Action order: calculating...")
        self.action_order_label.setWordWrap(True)
        self.advanced_opponents.setToolTip("Open the advanced opponent editor.")
        self.action_order_label.setToolTip("Current inferred action order.")
        footer_row = self.qtwidgets.QHBoxLayout()
        footer_row.addWidget(self.advanced_opponents)
        footer_row.addStretch(1)
        footer_row.addWidget(self.action_order_label)
        outer.addLayout(footer_row)

        _add_section_title("Cards")
        cards_group = self.qtwidgets.QGroupBox()
        cards_group.setObjectName("settingsCard")
        cards = self.qtwidgets.QFormLayout(cards_group)
        _configure_form_layout(cards)
        self.card_edits: list[Any] = []
        for slot in _CARD_SLOTS:
            row = self.qtwidgets.QHBoxLayout()
            edit = self.qtwidgets.QLineEdit()
            edit.setPlaceholderText("A♠")
            edit.setMaxLength(3)
            edit.setAccessibleName(slot)
            edit.setToolTip(f"Enter {slot.lower()} as A♠, T♥, AS, TH, or 10H.")
            pick = self.qtwidgets.QPushButton("Pick")
            pick.setToolTip(f"Choose {slot.lower()} from the deck.")
            pick.clicked.connect(lambda _checked=False, field=edit: self._pick_card(field))
            row.addWidget(edit, 1)
            row.addWidget(pick)
            # Use a QLabel for the form label to avoid automatic eliding/cropping
            label = self.qtwidgets.QLabel(slot)
            label.setMinimumWidth(label_width)
            label.setObjectName("cardLabel")
            label.setAlignment(
                self.qtcore.Qt.AlignmentFlag.AlignLeft | self.qtcore.Qt.AlignmentFlag.AlignVCenter
            )
            cards.addRow(label, row)
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
        panel.setObjectName("resultsPanel")
        layout = self.qtwidgets.QVBoxLayout(panel)
        layout.setSpacing(12)
        results_title = self.qtwidgets.QLabel("Results")
        results_title.setObjectName("sectionTitle")
        layout.addWidget(results_title)
        self.status_label = self.qtwidgets.QLabel("Ready")
        self.status_label.setObjectName("statusPill")
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
        bar = self.qtwidgets.QHBoxLayout()
        bar.setSpacing(12)

        primary_group = self.qtwidgets.QHBoxLayout()
        self.analyze_button = self._button("Analyze", "Alt+A", "Run the complete analysis.")
        self.analyze_button.setObjectName("primaryButton")
        primary_group.addWidget(self.analyze_button)
        bar.addLayout(primary_group)

        flow_group = self.qtwidgets.QHBoxLayout()
        self.cancel_button = self._button("Cancel", "Esc", "Cancel the active calculation.")
        self.clear_button = self._button(
            "Clear street", "", "Clear the latest entered board street."
        )
        self.new_button = self._button("New hand", "Ctrl+N", "Clear cards and analysis results.")
        flow_group.addWidget(self.cancel_button)
        flow_group.addWidget(self.clear_button)
        flow_group.addWidget(self.new_button)
        bar.addLayout(flow_group)

        file_group = self.qtwidgets.QHBoxLayout()
        self.save_button = self._button("Save", "Ctrl+S", "Save the current hand as JSON.")
        self.load_button = self._button("Load", "Ctrl+O", "Load a saved Peaceful Poker hand.")
        self.export_button = self._button("Export", "Ctrl+E", "Export the latest analysis.")
        file_group.addWidget(self.save_button)
        file_group.addWidget(self.load_button)
        file_group.addWidget(self.export_button)
        bar.addLayout(file_group)

        bar.addStretch(1)

        utility_group = self.qtwidgets.QHBoxLayout()
        self.settings_button = self._button("Settings", "", "Change theme and analysis defaults.")
        self.training_button = self._button("Training", "", "Load a generated practice scenario.")
        self.about_button = self._button(
            "Help / About", "F1", "Show application and limitation information."
        )
        utility_group.addWidget(self.settings_button)
        utility_group.addWidget(self.training_button)
        utility_group.addWidget(self.about_button)
        bar.addLayout(utility_group)

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
        return bar

    def _spinbox_styled(self, value: int, min_val: int = 0, max_val: int = 10) -> Any:
        """Create a QSpinBox with up/down buttons styled to match _money_spin."""
        spin = self.qtwidgets.QSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(value)
        spin.setButtonSymbols(self.qtwidgets.QAbstractSpinBox.UpDownArrows)
        spin.setStyleSheet(
            "QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {"
            " width: 20px; height: 20px; }"
            "QAbstractSpinBox::up-arrow, QAbstractSpinBox::down-arrow {"
            " width: 10px; height: 10px; }"
        )
        return spin

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
        spin.setButtonSymbols(self.qtwidgets.QAbstractSpinBox.UpDownArrows)
        spin.setStyleSheet(
            "QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {"
            " width: 20px; height: 20px; }"
            "QAbstractSpinBox::up-arrow, QAbstractSpinBox::down-arrow {"
            " width: 10px; height: 10px; }"
        )
        return spin

    def _stack_control(self, value: float) -> tuple[Any, Any]:
        spin = self.qtwidgets.QDoubleSpinBox()
        spin.setRange(0.0, 1_000_000.0)
        spin.setDecimals(2)
        spin.setSingleStep(1.0)
        spin.setValue(value)
        spin.setSuffix(" chips")
        spin.setButtonSymbols(self.qtwidgets.QAbstractSpinBox.NoButtons)
        spin.setFixedWidth(120)

        decrease_button = self.qtwidgets.QToolButton()
        decrease_button.setText("-")
        decrease_button.setFixedSize(26, 26)
        decrease_button.setCursor(self.qtcore.Qt.CursorShape.PointingHandCursor)
        decrease_button.clicked.connect(lambda _, s=spin: s.stepDown())

        increase_button = self.qtwidgets.QToolButton()
        increase_button.setText("+")
        increase_button.setFixedSize(26, 26)
        increase_button.setCursor(self.qtcore.Qt.CursorShape.PointingHandCursor)
        increase_button.clicked.connect(lambda _, s=spin: s.stepUp())

        container = self.qtwidgets.QWidget()
        layout = self.qtwidgets.QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(decrease_button)
        layout.addWidget(spin)
        layout.addWidget(increase_button)
        return container, spin

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

    def _normalize_card_text(self, text: str) -> str:
        normalized = text.strip().upper()
        if not normalized:
            return ""
        suit_code = _SYMBOL_TO_SUIT_CODE.get(normalized[-1])
        if suit_code is not None:
            return f"{normalized[:-1]}{suit_code}"
        return normalized

    def _display_card_text(self, card: Card) -> str:
        return card.code

    def _state(self) -> GameState:
        hero_text = [self._normalize_card_text(edit.text()) for edit in self.card_edits[:2]]
        if not all(hero_text):
            raise ValueError("Enter both hero cards before analyzing.")
        board_text = [self._normalize_card_text(edit.text()) for edit in self.card_edits[2:]]
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
        explanation = self.qtwidgets.QLabel(
            "Range selects the opponent hand distribution assumption. "
            "Previous selects the opponent's most recent action before hero."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        info_panel = self.qtwidgets.QFrame()
        info_panel.setObjectName("infoPanel")
        info_panel_layout = self.qtwidgets.QVBoxLayout(info_panel)
        info_panel_layout.setContentsMargins(14, 12, 14, 12)
        info_panel_layout.setSpacing(4)
        info_title = self.qtwidgets.QLabel("Column Info")
        info_title.setObjectName("infoPanelTitle")
        info_body = self.qtwidgets.QLabel("Click a header ⓘ to see what that column controls.")
        info_body.setObjectName("infoPanelBody")
        info_body.setWordWrap(True)
        info_panel_layout.addWidget(info_title)
        info_panel_layout.addWidget(info_body)
        layout.addWidget(info_panel)

        column_info = [
            ("Seat", "Zero-based seat number at the table."),
            ("Position", "Opponent table position for this round."),
            ("Folded", "Whether this opponent has folded and is no longer in the pot."),
            ("All-in", "Whether this opponent has committed their entire stack."),
            ("Stack", "Remaining chips available to this opponent before the decision."),
            ("Profile", "Behavioral profile that guides opponent decision making."),
            ("Range", "Estimated opponent hand range assumption for the current situation."),
            ("Previous", "Most recent action the opponent took before hero's turn."),
        ]
        editor = self.qtwidgets.QTableWidget(len(table_state.players), 8)
        editor.setHorizontalHeaderLabels([f"{title}  ⓘ" for title, _description in column_info])
        header = editor.horizontalHeader()
        header.setSectionsClickable(True)
        for index, (_title, description) in enumerate(column_info):
            header_item = editor.horizontalHeaderItem(index)
            if header_item is not None:
                header_item.setToolTip(description)

        def _show_column_info(section_index: int) -> None:
            title, description = column_info[section_index]
            info_title.setText(title)
            info_body.setText(description)

        header.sectionClicked.connect(_show_column_info)
        controls: dict[int, tuple[Any, Any, Any, Any, Any, Any, Any]] = {}
        for row, player in enumerate(table_state.players):
            seat_item = self.qtwidgets.QTableWidgetItem(str(player.seat))
            seat_item.setFlags(seat_item.flags() & ~self.qtcore.Qt.ItemFlag.ItemIsEditable)
            editor.setItem(row, 0, seat_item)
            position_combo = self.qtwidgets.QComboBox()
            for position_option in Position:
                position_combo.addItem(position_option.display_name, position_option.value)
            position_combo.setCurrentIndex(position_combo.findData(player.position))
            position_combo.setToolTip("Select the opponent's table position.")
            folded = self.qtwidgets.QCheckBox()
            folded.setChecked(player.folded)
            folded.setFocusPolicy(self.qtcore.Qt.FocusPolicy.StrongFocus)
            all_in = self.qtwidgets.QCheckBox()
            all_in.setChecked(player.all_in)
            all_in.setFocusPolicy(self.qtcore.Qt.FocusPolicy.StrongFocus)
            stack_widget, stack = self._stack_control(player.stack)
            profile = self.qtwidgets.QComboBox()
            for option in OpponentProfile:
                profile.addItem(option.display_name, option.value)
            profile.setCurrentIndex(profile.findData(player.profile.value))
            range_edit = self.qtwidgets.QComboBox()
            range_edit.setEditable(True)
            range_edit.addItems(list(_RANGE_OPTIONS))
            range_edit.setCurrentText(player.range_text or "random")
            range_edit.setToolTip("Select or enter an opponent range.")
            previous = self.qtwidgets.QComboBox()
            previous.addItems(list(_PREVIOUS_ACTION_OPTIONS))
            action_text = ", ".join(player.previous_actions) if player.previous_actions else "None"
            previous.setCurrentText(action_text)
            previous.setToolTip("Select the opponent's most recent action before hero.")
            if player.is_hero:
                folded.setEnabled(False)
                all_in.setEnabled(False)
                profile.setEnabled(False)
                range_edit.setEnabled(False)
                position_combo.setEnabled(False)
                previous.setEnabled(False)
            editor.setCellWidget(row, 1, position_combo)
            editor.setCellWidget(row, 2, folded)
            editor.setCellWidget(row, 3, all_in)
            editor.setCellWidget(row, 4, stack_widget)
            editor.setCellWidget(row, 5, profile)
            editor.setCellWidget(row, 6, range_edit)
            editor.setCellWidget(row, 7, previous)
            controls[player.seat] = (
                position_combo,
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
            position_combo, folded, all_in, stack, profile, range_edit, previous = controls[
                player.seat
            ]
            is_folded = folded.isChecked()
            is_all_in = all_in.isChecked() and not is_folded
            previous_text = previous.currentText().strip()
            actions = () if previous_text in ("", "None") else (previous_text,)
            overrides[player.seat] = replace(
                player,
                position=str(position_combo.currentData()) or player.position,
                folded=is_folded,
                all_in=is_all_in,
                stack=0.0 if is_all_in else float(stack.value()),
                profile=OpponentProfile(str(profile.currentData())),
                range_text=range_edit.currentText().strip() or "random",
                previous_actions=actions,
                eligible_to_act=not is_folded and not is_all_in,
                acted_this_round=bool(actions),
            )
        self.player_overrides = overrides
        self._input_changed()

    def _pick_card(self, field: Any) -> None:
        dialog = self.qtwidgets.QDialog(self.window)
        dialog.setWindowTitle("Select a Card")
        dialog.setObjectName("cardPickerDialog")
        dialog.setModal(True)
        layout = self.qtwidgets.QVBoxLayout(dialog)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)

        title = self.qtwidgets.QLabel("Choose a Card")
        title.setObjectName("cardPickerTitle")
        layout.addWidget(title)

        subtitle = self.qtwidgets.QLabel("Pick one available card from the deck")
        subtitle.setObjectName("cardPickerSubtitle")
        layout.addWidget(subtitle)

        grid_holder = self.qtwidgets.QWidget()
        grid_holder.setObjectName("cardPickerGrid")
        grid = self.qtwidgets.QGridLayout(grid_holder)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)

        suit_symbols = {
            Suit.SPADES: "♠",
            Suit.HEARTS: "♥",
            Suit.DIAMONDS: "♦",
            Suit.CLUBS: "♣",
        }

        for col, suit in enumerate(Suit, start=1):
            suit_header = self.qtwidgets.QLabel(suit_symbols[suit])
            suit_header.setObjectName("cardPickerSuitHeader")
            if suit in (Suit.HEARTS, Suit.DIAMONDS):
                suit_header.setProperty("redSuit", True)
            suit_header.setAlignment(self.qtcore.Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(suit_header, 0, col)

        used: set[Card] = set()
        for edit in self.card_edits:
            if edit is field or not edit.text().strip():
                continue
            try:
                used.add(Card.from_code(self._normalize_card_text(edit.text())))
            except Exception:  # noqa: BLE001 - invalid manual input is handled on analyze
                continue

        current_card: Card | None = None
        current_text = field.text().strip()
        if current_text:
            try:
                current_card = Card.from_code(self._normalize_card_text(current_text))
            except Exception:  # noqa: BLE001 - invalid manual input is handled on analyze
                current_card = None

        for row, rank in enumerate(reversed(tuple(Rank)), start=1):
            rank_header = self.qtwidgets.QLabel(rank.code)
            rank_header.setObjectName("cardPickerRankHeader")
            rank_header.setAlignment(self.qtcore.Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(rank_header, row, 0)

            for col, suit in enumerate(Suit, start=1):
                card = Card(rank, suit)
                button = self.qtwidgets.QPushButton()
                button.setObjectName("cardPickerCard")
                button.setFixedSize(88, 56)
                button.setCursor(self.qtcore.Qt.CursorShape.PointingHandCursor)
                button.setFocusPolicy(self.qtcore.Qt.FocusPolicy.StrongFocus)
                button.setAutoDefault(False)
                button.setDefault(False)
                if current_card is not None and card == current_card:
                    button.setProperty("selected", True)
                if card in used:
                    button.setProperty("used", True)

                content = self.qtwidgets.QHBoxLayout(button)
                content.setContentsMargins(0, 0, 0, 0)
                content.setSpacing(0)
                text_wrap = self.qtwidgets.QWidget()
                text_wrap.setObjectName("cardPickerCardText")
                text_wrap_layout = self.qtwidgets.QHBoxLayout(text_wrap)
                text_wrap_layout.setContentsMargins(0, 0, 0, 0)
                text_wrap_layout.setSpacing(0)

                rank_label = self.qtwidgets.QLabel(rank.code)
                rank_label.setObjectName("cardPickerRankText")
                rank_label.setAttribute(
                    self.qtcore.Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                    True,
                )
                suit_label = self.qtwidgets.QLabel(suit_symbols[suit])
                suit_label.setObjectName("cardPickerSuitText")
                if suit in (Suit.HEARTS, Suit.DIAMONDS):
                    suit_label.setProperty("redSuit", True)
                suit_label.setAttribute(
                    self.qtcore.Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                    True,
                )

                text_wrap_layout.addWidget(rank_label)
                text_wrap_layout.addWidget(suit_label)
                content.addWidget(text_wrap, 0, self.qtcore.Qt.AlignmentFlag.AlignCenter)

                button.setAccessibleName(card.display_name)
                button.setToolTip(card.display_name if card not in used else "Already used")
                button.setEnabled(card not in used)
                button.clicked.connect(
                    lambda _checked=False, selected=card: self._set_card(dialog, field, selected)
                )
                grid.addWidget(button, row, col)
        layout.addWidget(grid_holder)

        actions = self.qtwidgets.QDialogButtonBox(
            self.qtwidgets.QDialogButtonBox.StandardButton.Cancel
        )
        actions.rejected.connect(dialog.reject)
        layout.addWidget(actions)

        dialog.resize(500, 860)
        dialog.exec()

    def _set_card(self, dialog: Any, field: Any, card: Card) -> None:
        field.setText(self._display_card_text(card))
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
        players = self._spinbox_styled(self.settings.default_player_count, min_val=2, max_val=10)
        simulations = self.qtwidgets.QComboBox()
        for name, count in _PRESETS.items():
            simulations.addItem(f"{name} ({count:,})", count)
        simulations.setCurrentIndex(
            max(0, simulations.findData(self.settings.default_simulation_count))
        )
        precision = self._spinbox_styled(self.settings.percentage_precision, min_val=0, max_val=4)
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
            icon_path = resource_path("Logo.png")
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
            edit.setText(self._display_card_text(values[index]) if index < len(values) else "")
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
        for name, value in _THEME_TOKENS.get(selected, {}).items():
            stylesheet = stylesheet.replace(f"__{name.upper()}__", value)
        # Apply the resolved stylesheet and write a debug copy so it's easy to verify
        try:
            debug_path = "/tmp/peaceful_poker_applied.qss"
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(stylesheet)
            print(f"[DEBUG] Written resolved stylesheet to: {debug_path}")
        except Exception:
            pass
        self.window.setStyleSheet(stylesheet)

    def _toggle_sidebar(self) -> None:
        """Show or hide the navigation sidebar.

        If the app is currently showing the landing page, open the main area
        so the user can interact with the primary controls.
        """
        # If we're still on the landing page, show the main area first
        if (
            hasattr(self, "_landing_page")
            and hasattr(self, "_main_area")
            and self._main_area.isHidden()
        ):
            try:
                self._landing_page.hide()
                self._main_area.show()
            except Exception:
                pass
            # Ensure the sidebar is visible when opening the main area
            sidebar = getattr(self, "sidebar_widget", None)
            if sidebar is not None and not sidebar.isVisible():
                sidebar.show()
            return

        sidebar = getattr(self, "sidebar_widget", None)
        if sidebar is None:
            return
        sidebar.setVisible(not sidebar.isVisible())

    def _show_landing(self) -> None:
        """Switch back to the landing page and hide the main area."""
        if hasattr(self, "_landing_page") and hasattr(self, "_main_area"):
            try:
                self._main_area.hide()
                self._landing_page.show()
                if hasattr(self, "home_button"):
                    self.home_button.hide()
            except Exception:
                pass

    def _show_main_area(self) -> None:
        """Open the primary UI area and hide the landing page."""
        if hasattr(self, "_landing_page") and hasattr(self, "_main_area"):
            try:
                self._landing_page.hide()
                self._main_area.show()
                if hasattr(self, "home_button"):
                    self.home_button.show()
            except Exception:
                pass

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
