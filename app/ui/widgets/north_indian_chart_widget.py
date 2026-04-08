from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Union

from PyQt6.QtCore import QLineF, QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QPaintEvent, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from app.models.domain import ChartData


@dataclass(frozen=True)
class HouseCell:
    """
    Presentation-only coordinate container for one house.

    center:
        Main anchor point for house content.
    content_rect:
        Safe drawing box for house content.
    """

    number: int
    center: QPointF
    content_rect: QRectF


@dataclass(frozen=True)
class PlanetDisplay:
    """Minimal presentation data needed to render one planet in a house."""

    code: str
    house: int


@dataclass(frozen=True)
class ChartHeaderData:
    """Presentation metadata shown above the chart."""

    title: str = "North Indian Kundli"
    name: str = ""
    dob: str = ""
    tob: str = ""
    place: str = ""


class NorthIndianChartWidget(QWidget):
    """
    Reusable presentation widget for a North Indian horoscope chart.

    Step 1:
        Draw static chart frame.
    Step 2:
        Add fixed house mapping.
    Step 3:
        Accept chart data and render planet labels inside mapped houses.
    """

    MARGIN = 18.0
    BORDER_WIDTH = 2.0
    BACKGROUND_COLOR = QColor("#FFFDF7")
    BORDER_COLOR = QColor("#334155")
    LABEL_COLOR = QColor("#64748B")
    PLANET_TEXT_COLOR = QColor("#0F172A")
    TITLE_TEXT_COLOR = QColor("#1E293B")
    SUBTITLE_TEXT_COLOR = QColor("#475569")
    CARD_BORDER_COLOR = QColor("#CBD5E1")
    HEADER_GAP = 12.0
    HEADER_HEIGHT = 64.0

    HOUSE_CENTER_MAP = {
        1: (0.50, 0.25),
        2: (0.25, 0.15),
        3: (0.15, 0.25),
        4: (0.25, 0.50),
        5: (0.15, 0.75),
        6: (0.25, 0.85),
        7: (0.50, 0.75),
        8: (0.75, 0.85),
        9: (0.85, 0.75),
        10: (0.75, 0.50),
        11: (0.85, 0.25),
        12: (0.75, 0.15),
    }

    PLANET_ABBREVIATIONS = {
        "Sun": "Su",
        "Moon": "Mo",
        "Mars": "Ma",
        "Mercury": "Me",
        "Jupiter": "Ju",
        "Venus": "Ve",
        "Saturn": "Sa",
        "Rahu": "Ra",
        "Ketu": "Ke",
        "Ascendant": "As",
        "Lagna": "As",
    }

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(360, 360)
        self._show_house_labels = True
        self._house_cells: Dict[int, HouseCell] = {}
        self._planets_by_house: Dict[int, List[str]] = {house: [] for house in range(1, 13)}
        self._header_data = ChartHeaderData()

    def sizeHint(self) -> QSize:
        return QSize(420, 420)

    def set_show_house_labels(self, visible: bool) -> None:
        self._show_house_labels = visible
        self.update()

    def set_header_data(self, header_data: ChartHeaderData) -> None:
        self._header_data = header_data
        self.update()

    def clear_header_data(self) -> None:
        self._header_data = ChartHeaderData()
        self.update()

    def get_house_cells(self) -> Dict[int, HouseCell]:
        """Returns the current widget-space coordinate system for all houses."""
        return dict(self._house_cells)

    def get_house_cell(self, house_number: int) -> Optional[HouseCell]:
        return self._house_cells.get(house_number)

    def set_chart_data(self, chart_data: Sequence[Union[ChartData, dict]]) -> None:
        """
        Accepts raw chart rows and prepares presentation-only planet labels.

        Supported payloads:
        - app.models.domain.ChartData
        - dict objects like {"Planet": "Sun", "House": 1}
        """

        self._planets_by_house = {house: [] for house in range(1, 13)}

        for item in chart_data:
            planet = self._extract_planet_name(item)
            house = self._extract_house_number(item)
            if not planet or house is None or house not in self._planets_by_house:
                continue

            self._planets_by_house[house].append(self._abbreviate_planet(planet))

        self.update()

    def clear_chart_data(self) -> None:
        self._planets_by_house = {house: [] for house in range(1, 13)}
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), self.BACKGROUND_COLOR)

        self._draw_card_frame(painter)
        self._draw_header(painter)

        chart_rect = self._calculate_chart_rect()
        if chart_rect.width() <= 0 or chart_rect.height() <= 0:
            return

        self._house_cells = self._build_house_cells(chart_rect)

        self._draw_chart_frame(painter, chart_rect)

        if self._show_house_labels:
            self._draw_house_labels(painter)

        self._draw_planets(painter)

    def _calculate_chart_rect(self) -> QRectF:
        available_width = max(0.0, self.width() - (self.MARGIN * 2))
        available_height = max(
            0.0,
            self.height() - (self.MARGIN * 2) - self.HEADER_HEIGHT - self.HEADER_GAP,
        )
        side = max(0.0, min(available_width, available_height))
        x = (self.width() - side) / 2
        y = self.MARGIN + self.HEADER_HEIGHT + self.HEADER_GAP
        return QRectF(x, y, side, side)

    def _draw_card_frame(self, painter: QPainter) -> None:
        painter.save()
        painter.setPen(QPen(self.CARD_BORDER_COLOR, 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        frame_rect = QRectF(
            self.MARGIN / 2,
            self.MARGIN / 2,
            self.width() - self.MARGIN,
            self.height() - self.MARGIN,
        )
        painter.drawRoundedRect(frame_rect, 10.0, 10.0)
        painter.restore()

    def _draw_header(self, painter: QPainter) -> None:
        painter.save()

        title_rect = QRectF(
            self.MARGIN,
            self.MARGIN,
            self.width() - (self.MARGIN * 2),
            28,
        )
        subtitle_rect = QRectF(
            self.MARGIN,
            self.MARGIN + 30,
            self.width() - (self.MARGIN * 2),
            28,
        )

        painter.setPen(self.TITLE_TEXT_COLOR)
        painter.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        painter.drawText(
            title_rect,
            Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter,
            self._header_data.title,
        )

        subtitle_parts = [
            f"Name: {self._header_data.name}" if self._header_data.name else "",
            f"DOB: {self._header_data.dob}" if self._header_data.dob else "",
            f"TOB: {self._header_data.tob}" if self._header_data.tob else "",
            f"Place: {self._header_data.place}" if self._header_data.place else "",
        ]
        subtitle = "   |   ".join(part for part in subtitle_parts if part)

        if subtitle:
            painter.setPen(self.SUBTITLE_TEXT_COLOR)
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Medium))
            painter.drawText(
                subtitle_rect,
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter,
                subtitle,
            )

        painter.restore()

    def _draw_chart_frame(self, painter: QPainter, chart_rect: QRectF) -> None:
        painter.save()
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(self.BORDER_COLOR, self.BORDER_WIDTH))

        painter.drawRect(chart_rect)

        for line in self._build_frame_lines(chart_rect):
            painter.drawLine(line)

        painter.restore()

    def _build_frame_lines(self, chart_rect: QRectF) -> List[QLineF]:
        top_left = chart_rect.topLeft()
        top_right = chart_rect.topRight()
        bottom_right = chart_rect.bottomRight()
        bottom_left = chart_rect.bottomLeft()

        top_mid = QPointF(chart_rect.center().x(), chart_rect.top())
        right_mid = QPointF(chart_rect.right(), chart_rect.center().y())
        bottom_mid = QPointF(chart_rect.center().x(), chart_rect.bottom())
        left_mid = QPointF(chart_rect.left(), chart_rect.center().y())

        return [
            QLineF(top_left, bottom_right),
            QLineF(top_right, bottom_left),
            QLineF(top_mid, right_mid),
            QLineF(right_mid, bottom_mid),
            QLineF(bottom_mid, left_mid),
            QLineF(left_mid, top_mid),
        ]

    def _build_house_cells(self, chart_rect: QRectF) -> Dict[int, HouseCell]:
        cells: Dict[int, HouseCell] = {}
        side = chart_rect.width()

        box_width = side * 0.18
        box_height = side * 0.12

        for house_number, (rx, ry) in self.HOUSE_CENTER_MAP.items():
            center = QPointF(
                chart_rect.left() + (side * rx),
                chart_rect.top() + (side * ry),
            )
            content_rect = QRectF(
                center.x() - (box_width / 2),
                center.y() - (box_height / 2),
                box_width,
                box_height,
            )
            cells[house_number] = HouseCell(
                number=house_number,
                center=center,
                content_rect=content_rect,
            )

        return cells

    def _draw_house_labels(self, painter: QPainter) -> None:
        painter.save()
        painter.setPen(self.LABEL_COLOR)
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))

        for house_number in range(1, 13):
            cell = self._house_cells.get(house_number)
            if cell is None:
                continue

            label_rect = QRectF(
                cell.content_rect.left(),
                cell.content_rect.top() - 14,
                cell.content_rect.width(),
                12,
            )
            painter.drawText(
                label_rect,
                Qt.AlignmentFlag.AlignCenter,
                str(house_number),
            )

        painter.restore()

    def _draw_planets(self, painter: QPainter) -> None:
        painter.save()
        painter.setPen(self.PLANET_TEXT_COLOR)
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))

        for house_number, planet_codes in self._planets_by_house.items():
            if not planet_codes:
                continue

            cell = self._house_cells.get(house_number)
            if cell is None:
                continue

            text = self._format_planet_text(planet_codes)
            painter.drawText(
                cell.content_rect,
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap,
                text,
            )

        painter.restore()

    def _format_planet_text(self, planet_codes: List[str]) -> str:
        if len(planet_codes) <= 2:
            return " ".join(planet_codes)

        midpoint = (len(planet_codes) + 1) // 2
        first_line = " ".join(planet_codes[:midpoint])
        second_line = " ".join(planet_codes[midpoint:])
        return f"{first_line}\n{second_line}"

    def _extract_planet_name(self, item: Union[ChartData, dict]) -> Optional[str]:
        if isinstance(item, ChartData):
            return item.planet_name
        if isinstance(item, dict):
            return str(item.get("Planet") or item.get("planet_name") or "").strip() or None
        return None

    def _extract_house_number(self, item: Union[ChartData, dict]) -> Optional[int]:
        raw_house: Optional[object]
        if isinstance(item, ChartData):
            raw_house = item.house
        elif isinstance(item, dict):
            raw_house = item.get("House", item.get("house"))
        else:
            raw_house = None

        try:
            house = int(raw_house) if raw_house is not None else None
        except (TypeError, ValueError):
            return None
        return house

    def _abbreviate_planet(self, planet_name: str) -> str:
        normalized = planet_name.strip()
        if not normalized:
            return ""
        return self.PLANET_ABBREVIATIONS.get(normalized, normalized[:2].title())


class ChartPreviewWindow(QWidget):
    """Small standalone preview window for local visual testing."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("North Indian Chart Preview")

        layout = QVBoxLayout(self)

        title = QLabel("North Indian Chart - Planet Rendering")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self.chart_widget = NorthIndianChartWidget()
        layout.addWidget(self.chart_widget)
        self.chart_widget.set_header_data(
            ChartHeaderData(
                title="Birth Chart",
                name="Pinaki",
                dob="14-08-1995",
                tob="09:32",
                place="Kolkata",
            )
        )

        self.chart_widget.set_chart_data(
            [
                {"Planet": "Ascendant", "House": 1},
                {"Planet": "Sun", "House": 1},
                {"Planet": "Mercury", "House": 1},
                {"Planet": "Moon", "House": 4},
                {"Planet": "Mars", "House": 7},
                {"Planet": "Jupiter", "House": 9},
                {"Planet": "Saturn", "House": 10},
                {"Planet": "Rahu", "House": 11},
                {"Planet": "Ketu", "House": 5},
                {"Planet": "Venus", "House": 12},
            ]
        )


def main() -> int:
    app = QApplication(sys.argv)
    window = ChartPreviewWindow()
    window.resize(520, 560)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
