from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QLabel
)
from PyQt6.QtCore import pyqtSignal
from app.ui.theme import (
    SPACE_8,
    SPACE_12,
    SPACE_16,
    SPACE_24,
    fade_in_widget,
    set_button_icon,
    set_button_variant,
)

class UserListScreen(QWidget):
    # Signals for controller
    load_requested = pyqtSignal(int)
    delete_requested = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self._all_users_data: list[dict] = []
        self._busy = False
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(SPACE_24, SPACE_24, SPACE_24, SPACE_24)
        layout.setSpacing(SPACE_16)

        self.title_label = QLabel("Saved Profiles")
        self.title_label.setProperty("role", "title")
        self.subtitle_label = QLabel("Load, search, and manage saved user charts.")
        self.subtitle_label.setProperty("role", "subtitle")
        self.subtitle_label.setWordWrap(True)

        # Search bar area
        search_layout = QHBoxLayout()
        search_layout.setSpacing(SPACE_8)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by Name or Place...")
        self.search_input.setClearButtonEnabled(True)
        self.search_btn = QPushButton("Search")
        self.search_input.textChanged.connect(self._apply_search_filter)
        self.search_btn.clicked.connect(self._apply_search_filter)
        set_button_variant(self.search_btn, "ghost")
        set_button_icon(self.search_btn, "search")
        
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_btn)

        # Table area
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Date of Birth", "Place"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self._update_action_buttons)

        self.empty_state_label = QLabel("No saved profiles yet. Generate a chart to get started.")
        self.empty_state_label.setProperty("role", "empty-state")
        self.empty_state_label.setWordWrap(True)
        self.empty_state_label.setVisible(False)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(SPACE_8)
        self.btn_load = QPushButton("Load Chart")
        self.btn_delete = QPushButton("Delete User")
        set_button_variant(self.btn_load, "primary")
        set_button_variant(self.btn_delete, "danger")
        set_button_icon(self.btn_load, "load")
        set_button_icon(self.btn_delete, "delete")
        self.btn_load.setEnabled(False)
        self.btn_delete.setEnabled(False)
        
        # Connect internal actions
        self.btn_load.clicked.connect(self.on_load_clicked)
        self.btn_delete.clicked.connect(self.on_delete_clicked)

        btn_layout.addWidget(self.btn_load)
        btn_layout.addWidget(self.btn_delete)

        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle_label)
        layout.addLayout(search_layout)
        layout.addWidget(self.table)
        layout.addWidget(self.empty_state_label)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def populate_users(self, users_data: list):
        """Populates the UI table, expects list of dicts like {'id':1, 'name':'John', 'dob':'...', 'place':'...'}"""
        self._all_users_data = [dict(user) for user in users_data if isinstance(user, dict)]
        self._apply_search_filter()

    def _apply_search_filter(self):
        query = str(self.search_input.text() or "").strip().lower()
        if not query:
            filtered = list(self._all_users_data)
        else:
            filtered = []
            for user in self._all_users_data:
                haystack = " ".join(
                    [
                        str(user.get("name", "")),
                        str(user.get("place", "")),
                        str(user.get("city", "")),
                        str(user.get("state", "")),
                    ]
                ).lower()
                if query in haystack:
                    filtered.append(user)

        self.table.setRowCount(0) # Clear table
        for row_idx, user in enumerate(filtered):
            self.table.insertRow(row_idx)
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(user.get("id"))))
            self.table.setItem(row_idx, 1, QTableWidgetItem(str(user.get("name", ""))))
            self.table.setItem(row_idx, 2, QTableWidgetItem(str(user.get("dob", ""))))
            self.table.setItem(row_idx, 3, QTableWidgetItem(str(user.get("place", ""))))

        self._update_empty_state(filtered, query)
        self._update_action_buttons()

    def _get_selected_user_id(self):
        selected_items = self.table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Selection Error", "Please select a user from the list.")
            return None
        # ID is always in column 0
        row = selected_items[0].row()
        id_item = self.table.item(row, 0)
        return int(id_item.text())

    def on_load_clicked(self):
        user_id = self._get_selected_user_id()
        if user_id is not None:
            self.load_requested.emit(user_id)

    def on_delete_clicked(self):
        user_id = self._get_selected_user_id()
        if user_id is not None:
            # Confirm deletion visually
            reply = QMessageBox.question(
                self, 'Confirm Deletion', 'Are you sure you want to delete this user?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.delete_requested.emit(user_id)

    def _update_empty_state(self, filtered: list[dict], query: str) -> None:
        if self._busy:
            self.empty_state_label.setVisible(False)
            return

        if not self._all_users_data:
            self.empty_state_label.setText("No saved profiles yet. Generate a chart to get started.")
            self.empty_state_label.setVisible(True)
            fade_in_widget(self.empty_state_label)
            return

        if not filtered:
            self.empty_state_label.setText(f'No profiles found for "{query}".')
            self.empty_state_label.setVisible(True)
            fade_in_widget(self.empty_state_label)
            return

        self.empty_state_label.setVisible(False)

    def _update_action_buttons(self) -> None:
        has_selection = bool(self.table.selectedItems())
        self.btn_load.setEnabled(has_selection and not self._busy)
        self.btn_delete.setEnabled(has_selection and not self._busy)

    def set_busy(self, busy: bool, mode: str = "refresh") -> None:
        """Shows feedback during load/delete/refresh operations."""
        self._busy = bool(busy)
        self.search_input.setEnabled(not self._busy)
        self.search_btn.setEnabled(not self._busy)
        self.table.setEnabled(not self._busy)

        if self._busy:
            normalized = str(mode or "").strip().lower()
            if normalized == "load":
                self.btn_load.setText("Loading...")
            elif normalized == "delete":
                self.btn_delete.setText("Deleting...")
            else:
                self.search_btn.setText("Refreshing...")
                set_button_icon(self.search_btn, "refresh")
            self.empty_state_label.setVisible(False)
            self._update_action_buttons()
            return

        self.search_btn.setText("Search")
        set_button_icon(self.search_btn, "search")
        self.btn_load.setText("Load Chart")
        self.btn_delete.setText("Delete User")
        self._apply_search_filter()
