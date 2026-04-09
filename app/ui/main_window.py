import os

from PyQt6.QtWidgets import QHBoxLayout, QMainWindow, QTabWidget, QWidget
from app.services.language_manager import LanguageManager
from app.ui.input_form import InputForm
from app.ui.chart_display import ChartDisplay

class MainWindow(QMainWindow):
    def __init__(self, db_manager=None, language_manager: LanguageManager | None = None):
        super().__init__()
        self.db_manager = db_manager
        self.language_manager = language_manager or LanguageManager()
        self.debug_ui_enabled = str(os.getenv("HOROSCOPE_DEBUG_UI", "")).strip().lower() in {"1", "true", "yes", "on"}
        self.setWindowTitle(self.language_manager.get_text("ui.app_title"))
        self.resize(1240, 820)
        self.setMinimumSize(1080, 720)

        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(16)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(False)

        # --- TAB 1: Chart Generator --- #
        self.chart_gen_tab = QWidget()
        chart_layout = QHBoxLayout()
        chart_layout.setContentsMargins(16, 16, 16, 16)
        chart_layout.setSpacing(16)

        self.input_form = InputForm(self.language_manager)
        self.chart_display = ChartDisplay(self.language_manager)

        # The signals (generate_requested, save_requested) will be connected by the MainController

        chart_layout.addWidget(self.input_form, 1)      # takes 1 part of width
        chart_layout.addWidget(self.chart_display, 2)   # takes 2 parts of width
        self.chart_gen_tab.setLayout(chart_layout)

        # --- TAB 2: User Management --- #
        from app.ui.user_list_screen import UserListScreen
        self.user_list_screen = UserListScreen()

        # --- TAB 3: Rule Editor --- #
        from app.ui.rule_editor_screen import RuleEditorScreen
        self.rule_editor_screen = RuleEditorScreen()

        # --- ADVANCED TABS (Read-Only) --- #
        from PyQt6.QtWidgets import QTextEdit
        self.aspects_view = QTextEdit()
        self.aspects_view.setReadOnly(True)
        
        self.dasha_view = QTextEdit()
        self.dasha_view.setReadOnly(True)
        
        from app.ui.widgets.navamsha_widget import NavamshaWidget
        self.navamsha_view = NavamshaWidget(language_manager=self.language_manager)
        
        self.plugins_view = QTextEdit()
        self.plugins_view.setReadOnly(True)
        self.transits_view = QTextEdit()
        self.transits_view.setReadOnly(True)
        self.shadbala_view = QTextEdit()
        self.shadbala_view.setReadOnly(True)

        from app.ui.widgets.timeline_widget import TimelineWidget
        self.timeline_view = TimelineWidget()

        from app.ui.chat_screen import ChatScreen
        self.chat_screen = ChatScreen()

        from app.ui.settings_screen import SettingsScreen
        self.settings_screen = SettingsScreen(self.language_manager)

        # Primary product tabs
        self.tabs.addTab(self.chart_gen_tab, "")
        self.tabs.addTab(self.timeline_view, "")
        self.tabs.addTab(self.chat_screen, "")
        self.tabs.addTab(self.user_list_screen, "")
        self.tabs.addTab(self.settings_screen, "")

        # Internal analysis tabs (debug only)
        if self.debug_ui_enabled:
            self.tabs.addTab(self.rule_editor_screen, "")
            self.tabs.addTab(self.aspects_view, "")
            self.tabs.addTab(self.dasha_view, "")
            self.tabs.addTab(self.transits_view, "")
            self.tabs.addTab(self.shadbala_view, "")
            self.tabs.addTab(self.navamsha_view, "")
            self.tabs.addTab(self.plugins_view, "")

        layout.addWidget(self.tabs)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)
        self.apply_translations()

    def apply_translations(self) -> None:
        self.setWindowTitle(self.language_manager.get_text("ui.app_title"))
        tab_labels = [
            self.language_manager.get_text("ui.chart_generator"),
            self.language_manager.get_text("ui.life_timeline"),
            self.language_manager.get_text("ui.horoscope_chat"),
            self.language_manager.get_text("ui.user_management"),
            self.language_manager.get_text("ui.settings"),
        ]
        if self.debug_ui_enabled:
            tab_labels.extend(
                [
                    self.language_manager.get_text("ui.rule_editor"),
                    self.language_manager.get_text("ui.aspects"),
                    self.language_manager.get_text("ui.dasha"),
                    self.language_manager.get_text("ui.transits"),
                    self.language_manager.get_text("ui.shadbala"),
                    self.language_manager.get_text("ui.navamsha_d9"),
                    self.language_manager.get_text("ui.plugins"),
                ]
            )

        for index, label in enumerate(tab_labels):
            self.tabs.setTabText(index, label)
        self.input_form.apply_translations()
        self.chart_display.apply_translations()
        self.settings_screen.apply_translations()
        self.navamsha_view.apply_translations()
