from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox
)
from PyQt6.QtCore import pyqtSignal

class UserListScreen(QWidget):
    # Signals for controller
    load_requested = pyqtSignal(int)
    delete_requested = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Search bar area
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by Name or Place...")
        self.search_btn = QPushButton("Search")
        
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_btn)

        # Table area
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Date of Birth", "Place"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        # Action Buttons
        btn_layout = QHBoxLayout()
        self.btn_load = QPushButton("Load Chart")
        self.btn_delete = QPushButton("Delete User")
        
        # Connect internal actions
        self.btn_load.clicked.connect(self.on_load_clicked)
        self.btn_delete.clicked.connect(self.on_delete_clicked)

        btn_layout.addWidget(self.btn_load)
        btn_layout.addWidget(self.btn_delete)

        layout.addLayout(search_layout)
        layout.addWidget(self.table)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def populate_users(self, users_data: list):
        """Populates the UI table, expects list of dicts like {'id':1, 'name':'John', 'dob':'...', 'place':'...'}"""
        self.table.setRowCount(0) # Clear table
        for row_idx, user in enumerate(users_data):
            self.table.insertRow(row_idx)
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(user.get("id"))))
            self.table.setItem(row_idx, 1, QTableWidgetItem(user.get("name")))
            self.table.setItem(row_idx, 2, QTableWidgetItem(user.get("dob")))
            self.table.setItem(row_idx, 3, QTableWidgetItem(user.get("place")))

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
