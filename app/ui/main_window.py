from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QMessageBox, QTabWidget
from app.services.language_manager import LanguageManager
from app.ui.input_form import InputForm
from app.ui.chart_display import ChartDisplay

class MainWindow(QMainWindow):
    def __init__(self, db_manager=None, language_manager: LanguageManager | None = None):
        super().__init__()
        self.db_manager = db_manager
        self.language_manager = language_manager or LanguageManager()
        self.setWindowTitle(self.language_manager.get_text("ui.app_title"))
        self.resize(1000, 600)

        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        layout = QHBoxLayout()

        # We'll use a QTabWidget as the primary structure
        self.tabs = QTabWidget()

        # --- TAB 1: Chart Generator --- #
        self.chart_gen_tab = QWidget()
        chart_layout = QHBoxLayout()

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

        from app.ui.widgets.timeline_widget import TimelineWidget
        self.timeline_view = TimelineWidget()

        from app.ui.chat_screen import ChatScreen
        self.chat_screen = ChatScreen()

        from app.ui.settings_screen import SettingsScreen
        self.settings_screen = SettingsScreen(self.language_manager)

        # Add tabs
        self.tabs.addTab(self.chart_gen_tab, "")
        self.tabs.addTab(self.user_list_screen, "")
        self.tabs.addTab(self.rule_editor_screen, "")
        self.tabs.addTab(self.chat_screen, "")
        self.tabs.addTab(self.aspects_view, "")
        self.tabs.addTab(self.dasha_view, "")
        self.tabs.addTab(self.timeline_view, "")
        self.tabs.addTab(self.navamsha_view, "")
        self.tabs.addTab(self.plugins_view, "")
        self.tabs.addTab(self.settings_screen, "")

        layout.addWidget(self.tabs)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)
        self.apply_translations()

    def apply_translations(self) -> None:
        self.setWindowTitle(self.language_manager.get_text("ui.app_title"))
        self.tabs.setTabText(0, self.language_manager.get_text("ui.chart_generator"))
        self.tabs.setTabText(1, self.language_manager.get_text("ui.user_management"))
        self.tabs.setTabText(2, self.language_manager.get_text("ui.rule_editor"))
        self.tabs.setTabText(3, self.language_manager.get_text("ui.horoscope_chat"))
        self.tabs.setTabText(4, self.language_manager.get_text("ui.aspects"))
        self.tabs.setTabText(5, self.language_manager.get_text("ui.dasha"))
        self.tabs.setTabText(6, self.language_manager.get_text("ui.life_timeline"))
        self.tabs.setTabText(7, self.language_manager.get_text("ui.navamsha_d9"))
        self.tabs.setTabText(8, self.language_manager.get_text("ui.plugins"))
        self.tabs.setTabText(9, self.language_manager.get_text("ui.settings"))
        self.input_form.apply_translations()
        self.chart_display.apply_translations()
        self.settings_screen.apply_translations()
        self.navamsha_view.apply_translations()

# The controller will bind handlers directly to self.input_form.generate_requested and self.input_form.save_requested.
        # No internal logic needed here in MainWindow.
