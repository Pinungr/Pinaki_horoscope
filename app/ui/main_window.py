from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QMessageBox, QTabWidget
from app.ui.input_form import InputForm
from app.ui.chart_display import ChartDisplay

class MainWindow(QMainWindow):
    def __init__(self, db_manager=None):
        super().__init__()
        self.db_manager = db_manager
        self.setWindowTitle("Offline Horoscope (Kundli) Engine")
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

        self.input_form = InputForm()
        self.chart_display = ChartDisplay()

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
        
        self.navamsha_view = QTextEdit()
        self.navamsha_view.setReadOnly(True)
        
        self.plugins_view = QTextEdit()
        self.plugins_view.setReadOnly(True)

        from app.ui.widgets.timeline_widget import TimelineWidget
        self.timeline_view = TimelineWidget()

        from app.ui.chat_screen import ChatScreen
        self.chat_screen = ChatScreen()

        from app.ui.settings_screen import SettingsScreen
        self.settings_screen = SettingsScreen()

        # Add tabs
        self.tabs.addTab(self.chart_gen_tab, "Chart Generator")
        self.tabs.addTab(self.user_list_screen, "User Management")
        self.tabs.addTab(self.rule_editor_screen, "Rule Editor")
        self.tabs.addTab(self.chat_screen, "Horoscope Chat")
        self.tabs.addTab(self.aspects_view, "Aspects")
        self.tabs.addTab(self.dasha_view, "Dasha")
        self.tabs.addTab(self.timeline_view, "Life Timeline")
        self.tabs.addTab(self.navamsha_view, "Navamsha D9")
        self.tabs.addTab(self.plugins_view, "Plugins")
        self.tabs.addTab(self.settings_screen, "Settings")

        layout.addWidget(self.tabs)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

# The controller will bind handlers directly to self.input_form.generate_requested and self.input_form.save_requested.
        # No internal logic needed here in MainWindow.
