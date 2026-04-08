from __future__ import annotations

from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.services.language_manager import LanguageManager


# ---------------------------------------------------------------------------
# Color palette — mirrors the NorthIndianChartWidget planet color scheme
# ---------------------------------------------------------------------------
_PLANET_COLORS: Dict[str, str] = {
    "Ascendant": "#7C3AED",
    "Sun": "#EA580C",
    "Moon": "#2563EB",
    "Mars": "#DC2626",
    "Mercury": "#059669",
    "Jupiter": "#D97706",
    "Venus": "#DB2777",
    "Saturn": "#475569",
    "Rahu": "#0F766E",
    "Ketu": "#7C2D12",
}

_SIGN_ELEMENT: Dict[str, str] = {
    "Aries": "fire", "Leo": "fire", "Sagittarius": "fire",
    "Taurus": "earth", "Virgo": "earth", "Capricorn": "earth",
    "Gemini": "air", "Libra": "air", "Aquarius": "air",
    "Cancer": "water", "Scorpio": "water", "Pisces": "water",
}

_ELEMENT_BG: Dict[str, str] = {
    "fire":  "#fff7ed",
    "earth": "#f0fdf4",
    "air":   "#f0f9ff",
    "water": "#eff6ff",
}

_ELEMENT_BORDER: Dict[str, str] = {
    "fire":  "#fdba74",
    "earth": "#86efac",
    "air":   "#7dd3fc",
    "water": "#93c5fd",
}


def _sign_bg(sign: str) -> str:
    return _ELEMENT_BG.get(_SIGN_ELEMENT.get(sign, ""), "#f8fafc")


def _sign_border(sign: str) -> str:
    return _ELEMENT_BORDER.get(_SIGN_ELEMENT.get(sign, ""), "#e2e8f0")


# ---------------------------------------------------------------------------
# Small reusable sub-widgets
# ---------------------------------------------------------------------------

class _PlanetPill(QLabel):
    """Compact colored badge showing a planet name."""

    def __init__(self, planet_name: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(planet_name[:3], parent)
        color = _PLANET_COLORS.get(planet_name, "#64748b")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setToolTip(planet_name)
        self.setStyleSheet(
            f"""
            QLabel {{
                color: {color};
                background: transparent;
                border: 1px solid {color};
                border-radius: 4px;
                padding: 1px 4px;
            }}
            """
        )


class _SignCard(QFrame):
    """
    Card for one Navamsha sign cell.
    Shows:
      ┌─────────────────┐
      │  ♋ Cancer       │   ← sign name (coloured by element)
      │  [Sun] [Moon]   │   ← planet pills
      └─────────────────┘
    """

    def __init__(
        self,
        sign: str,
        planets: List[str],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        bg = _sign_bg(sign)
        border = _sign_border(sign)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            f"""
            QFrame {{
                background: {bg};
                border: 1.5px solid {border};
                border-radius: 10px;
            }}
            """
        )
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(72)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        sign_label = QLabel(sign)
        sign_label.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        sign_label.setStyleSheet("color: #334155; background: transparent; border: none;")
        layout.addWidget(sign_label)

        if planets:
            pill_row = QHBoxLayout()
            pill_row.setContentsMargins(0, 0, 0, 0)
            pill_row.setSpacing(4)
            for p in sorted(planets):
                pill_row.addWidget(_PlanetPill(p))
            pill_row.addStretch()
            layout.addLayout(pill_row)
        else:
            empty = QLabel("—")
            empty.setStyleSheet("color: #94a3b8; background: transparent; border: none; font-size: 11px;")
            layout.addWidget(empty)


# ---------------------------------------------------------------------------
# Main widget
# ---------------------------------------------------------------------------

class NavamshaWidget(QWidget):
    """
    Visual Navamsha (D9) chart widget.

    Accepts navamsha data in the format produced by NavamshaEngine:
        {"Sun": {"navamsha_sign": "Gemini"}, "Moon": {"navamsha_sign": "Cancer"}, ...}

    Displays a responsive 4-column grid of all 12 zodiac signs,
    with planet pills placed inside their respective D9 sign cells.
    """

    ZODIAC_ORDER: List[str] = [
        "Aries", "Taurus", "Gemini", "Cancer",
        "Leo", "Virgo", "Libra", "Scorpio",
        "Sagittarius", "Capricorn", "Aquarius", "Pisces",
    ]

    def __init__(
        self,
        language_manager: Optional[LanguageManager] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.language_manager = language_manager or LanguageManager()
        self._navamsha_data: Dict[str, Any] = {}
        self._init_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_navamsha_data(self, data: Dict[str, Any]) -> None:
        """
        Accepts the raw dict from NavamshaEngine.
        Keys are planet names; values are dicts with 'navamsha_sign'.
        """
        self._navamsha_data = dict(data) if isinstance(data, dict) else {}
        self._rebuild()

    def clear(self) -> None:
        self._navamsha_data = {}
        self._rebuild()

    def apply_translations(self) -> None:
        self._header_title.setText(self._tr("ui.navamsha_d9"))
        self._subtitle.setText(self._tr("chart.house"))  # reuse closest key

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _tr(self, key: str) -> str:
        return self.language_manager.get_text(key)

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        # --- Header ---
        header_row = QHBoxLayout()
        self._header_title = QLabel(self._tr("ui.navamsha_d9"))
        self._header_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self._header_title.setStyleSheet("color: #1e293b;")

        self._subtitle = QLabel("D9 — Navamsha divisional chart placements")
        self._subtitle.setFont(QFont("Segoe UI", 9))
        self._subtitle.setStyleSheet("color: #64748b;")

        header_row.addWidget(self._header_title)
        header_row.addStretch()
        header_row.addWidget(self._subtitle)

        # --- Legend ---
        legend = self._build_legend()

        # --- Scrollable grid area ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        self._grid_container = QWidget()
        self._grid_container.setStyleSheet("background: transparent;")
        self._grid_layout = QGridLayout(self._grid_container)
        self._grid_layout.setSpacing(10)
        self._grid_layout.setContentsMargins(0, 0, 0, 0)

        scroll.setWidget(self._grid_container)

        # --- Empty state label ---
        self._empty_label = QLabel("No Navamsha data available. Generate a chart first.")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("color: #94a3b8; font-size: 13px; padding: 24px;")
        self._empty_label.hide()

        root.addLayout(header_row)
        root.addWidget(legend)
        root.addWidget(scroll)
        root.addWidget(self._empty_label)

        self._scroll = scroll
        self._rebuild()

    def _build_legend(self) -> QWidget:
        """Builds a small element-color legend strip."""
        row = QHBoxLayout()
        row.setSpacing(16)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel("Element:"))
        for element, bg, border, label in (
            ("fire",  _ELEMENT_BG["fire"],  _ELEMENT_BORDER["fire"],  "Fire"),
            ("earth", _ELEMENT_BG["earth"], _ELEMENT_BORDER["earth"], "Earth"),
            ("air",   _ELEMENT_BG["air"],   _ELEMENT_BORDER["air"],   "Air"),
            ("water", _ELEMENT_BG["water"], _ELEMENT_BORDER["water"], "Water"),
        ):
            chip = QLabel(f"  {label}  ")
            chip.setFont(QFont("Segoe UI", 8))
            chip.setStyleSheet(
                f"background: {bg}; border: 1.5px solid {border}; border-radius: 4px; padding: 1px 4px; color: #334155;"
            )
            row.addWidget(chip)
        row.addStretch()

        container = QWidget()
        container.setLayout(row)
        return container

    def _rebuild(self) -> None:
        """Clears and redraws the 4-column sign grid."""
        # Remove all existing grid items
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        if not self._navamsha_data:
            self._scroll.hide()
            self._empty_label.show()
            return

        self._empty_label.hide()
        self._scroll.show()

        # Map sign → list of planets in that sign
        sign_to_planets: Dict[str, List[str]] = {sign: [] for sign in self.ZODIAC_ORDER}
        for planet, info in self._navamsha_data.items():
            if not isinstance(info, dict):
                continue
            navamsha_sign = str(info.get("navamsha_sign", "")).strip()
            if navamsha_sign in sign_to_planets:
                sign_to_planets[navamsha_sign].append(planet)

        # Lay out in 4 columns
        columns = 4
        for idx, sign in enumerate(self.ZODIAC_ORDER):
            row = idx // columns
            col = idx % columns
            card = _SignCard(sign, sign_to_planets[sign])
            self._grid_layout.addWidget(card, row, col)


# ---------------------------------------------------------------------------
# Standalone preview
# ---------------------------------------------------------------------------

def _preview() -> None:
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    w = NavamshaWidget()
    w.setWindowTitle("Navamsha D9 Widget Preview")
    w.resize(700, 500)

    sample = {
        "Sun":      {"navamsha_sign": "Leo"},
        "Moon":     {"navamsha_sign": "Cancer"},
        "Mars":     {"navamsha_sign": "Aries"},
        "Mercury":  {"navamsha_sign": "Libra"},
        "Jupiter":  {"navamsha_sign": "Sagittarius"},
        "Venus":    {"navamsha_sign": "Taurus"},
        "Saturn":   {"navamsha_sign": "Capricorn"},
        "Rahu":     {"navamsha_sign": "Cancer"},
        "Ketu":     {"navamsha_sign": "Capricorn"},
        "Ascendant":{"navamsha_sign": "Leo"},
    }
    w.set_navamsha_data(sample)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    _preview()
