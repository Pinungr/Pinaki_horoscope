from __future__ import annotations

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QSize
from PyQt6.QtWidgets import QApplication, QGraphicsOpacityEffect, QStyle, QWidget


SPACE_4 = 4
SPACE_8 = 8
SPACE_12 = 12
SPACE_16 = 16
SPACE_24 = 24
SPACE_32 = 32

RADIUS_SM = 8
RADIUS_MD = 10
RADIUS_LG = 14

COLOR_BG = "#f5f7fb"
COLOR_SURFACE = "#ffffff"
COLOR_SURFACE_MUTED = "#f8fafc"
COLOR_BORDER = "#dbe3ef"
COLOR_TEXT = "#0f172a"
COLOR_TEXT_MUTED = "#475569"
COLOR_PRIMARY = "#2563eb"
COLOR_PRIMARY_HOVER = "#1d4ed8"
COLOR_PRIMARY_PRESSED = "#1e40af"
COLOR_DANGER = "#dc2626"
COLOR_DANGER_HOVER = "#b91c1c"
COLOR_SUCCESS = "#16a34a"
COLOR_WARNING = "#d97706"


APP_STYLESHEET = f"""
QWidget {{
    background: {COLOR_BG};
    color: {COLOR_TEXT};
    font-family: "Segoe UI Variable", "Segoe UI", "Inter";
    font-size: 13px;
}}

QMainWindow {{
    background: {COLOR_BG};
}}

QFrame#Card {{
    background: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_LG}px;
}}

QFrame[role="insight-card"] {{
    background: #f8fafc;
    border: 1px solid #dbe3ef;
    border-radius: 12px;
}}

QFrame[role="insight-card"]:hover {{
    background: #f1f5f9;
    border: 1px solid #bfdbfe;
}}

QLabel[role="title"] {{
    font-size: 20px;
    font-weight: 700;
    color: {COLOR_TEXT};
}}

QLabel[role="subtitle"] {{
    font-size: 12px;
    color: {COLOR_TEXT_MUTED};
}}

QLabel[role="empty-state"] {{
    color: #64748b;
    font-size: 12px;
    background: #f8fafc;
    border: 1px dashed #cbd5e1;
    border-radius: {RADIUS_MD}px;
    padding: 8px 12px;
}}

QLineEdit, QComboBox, QDateEdit, QTimeEdit, QTextEdit, QSpinBox, QDoubleSpinBox {{
    background: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_MD}px;
    padding: 6px 10px;
    min-height: 30px;
    selection-background-color: {COLOR_PRIMARY};
    selection-color: #ffffff;
}}

QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QTimeEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {COLOR_PRIMARY};
}}

QPushButton {{
    background: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_MD}px;
    color: {COLOR_TEXT};
    min-height: 34px;
    padding: 6px 12px;
    font-weight: 600;
}}

QPushButton:hover {{
    background: {COLOR_SURFACE_MUTED};
    border: 1px solid #cfd8e6;
}}

QPushButton:pressed {{
    background: #eef2f7;
}}

QPushButton[variant="primary"] {{
    background: {COLOR_PRIMARY};
    color: #ffffff;
    border: 1px solid {COLOR_PRIMARY};
}}

QPushButton[variant="primary"]:hover {{
    background: {COLOR_PRIMARY_HOVER};
    border: 1px solid {COLOR_PRIMARY_HOVER};
}}

QPushButton[variant="primary"]:pressed {{
    background: {COLOR_PRIMARY_PRESSED};
    border: 1px solid {COLOR_PRIMARY_PRESSED};
}}

QPushButton[variant="danger"] {{
    background: {COLOR_DANGER};
    color: #ffffff;
    border: 1px solid {COLOR_DANGER};
}}

QPushButton[variant="danger"]:hover {{
    background: {COLOR_DANGER_HOVER};
    border: 1px solid {COLOR_DANGER_HOVER};
}}

QPushButton[variant="ghost"] {{
    background: transparent;
    color: {COLOR_TEXT_MUTED};
    border: 1px solid transparent;
}}

QPushButton[chip="true"] {{
    background: #eef2ff;
    color: #3730a3;
    border: 1px solid #c7d2fe;
    border-radius: 12px;
    min-height: 28px;
    padding: 4px 10px;
    font-size: 11px;
}}

QPushButton[chip="true"]:hover {{
    background: #e0e7ff;
    border: 1px solid #a5b4fc;
}}

QTableWidget {{
    background: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_MD}px;
    gridline-color: #edf2f7;
    alternate-background-color: #f8fafc;
}}

QHeaderView::section {{
    background: #f1f5f9;
    color: {COLOR_TEXT_MUTED};
    border: 0px;
    border-bottom: 1px solid {COLOR_BORDER};
    padding: 8px 6px;
    font-weight: 700;
}}

QTabWidget::pane {{
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_MD}px;
    background: {COLOR_SURFACE};
    top: -1px;
}}

QTabBar::tab {{
    background: #eef2f7;
    color: {COLOR_TEXT_MUTED};
    padding: 8px 14px;
    margin-right: 4px;
    border-top-left-radius: {RADIUS_MD}px;
    border-top-right-radius: {RADIUS_MD}px;
}}

QTabBar::tab:selected {{
    background: {COLOR_SURFACE};
    color: {COLOR_TEXT};
    font-weight: 700;
}}

QScrollArea {{
    border: none;
    background: transparent;
}}
"""


def apply_app_theme(app: QApplication) -> None:
    """Applies the global design system stylesheet to the whole app."""
    app.setStyleSheet(APP_STYLESHEET)


def set_button_variant(widget: QWidget, variant: str) -> None:
    """Applies a semantic button variant and refreshes style state."""
    widget.setProperty("variant", str(variant or "").strip().lower())
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def set_button_icon(widget: QWidget, name: str, size: int = 16) -> None:
    """Applies a consistent built-in icon set so actions feel visually unified."""
    key = str(name or "").strip().lower()
    pix = QStyle.StandardPixmap

    def _first_pixmap(*candidates: str):
        for candidate in candidates:
            resolved = getattr(pix, candidate, None)
            if resolved is not None:
                return resolved
        return None

    icon_map = {
        "add": _first_pixmap("SP_FileDialogNewFolder", "SP_DialogApplyButton"),
        "generate": _first_pixmap("SP_DialogApplyButton", "SP_MediaPlay"),
        "save": _first_pixmap("SP_DialogSaveButton", "SP_DialogApplyButton"),
        "search": _first_pixmap("SP_FileDialogContentsView", "SP_FileDialogDetailedView"),
        "load": _first_pixmap("SP_DialogOpenButton", "SP_ArrowForward", "SP_ArrowRight"),
        "delete": _first_pixmap("SP_TrashIcon", "SP_DialogCancelButton"),
        "send": _first_pixmap("SP_ArrowForward", "SP_ArrowRight"),
        "why": _first_pixmap("SP_MessageBoxQuestion", "SP_MessageBoxInformation"),
        "report": _first_pixmap("SP_DialogSaveButton", "SP_FileDialogDetailedView"),
        "zoom_in": _first_pixmap("SP_ArrowUp"),
        "zoom_out": _first_pixmap("SP_ArrowDown"),
        "reset": _first_pixmap("SP_BrowserReload"),
        "refresh": _first_pixmap("SP_BrowserReload"),
    }

    pixmap = icon_map.get(key)
    if pixmap is None:
        return
    widget.setIcon(widget.style().standardIcon(pixmap))
    widget.setIconSize(QSize(max(12, int(size)), max(12, int(size))))


def fade_in_widget(widget: QWidget, duration_ms: int = 160) -> None:
    """Runs a subtle fade-in reveal for status and empty-state widgets."""
    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsOpacityEffect):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)

    animation = QPropertyAnimation(effect, b"opacity", widget)
    animation.setDuration(max(80, int(duration_ms)))
    animation.setStartValue(0.15)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    animation.start()
    widget._fade_animation = animation  # type: ignore[attr-defined]
