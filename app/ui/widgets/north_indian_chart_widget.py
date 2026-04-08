from __future__ import annotations

import sys
import math
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Union

from PyQt6.QtCore import QLineF, QPoint, QPointF, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QMouseEvent, QPaintEvent, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QLabel, QToolTip, QVBoxLayout, QWidget

from app.models.domain import ChartData
from app.services.language_manager import LanguageManager


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
    name: str = ""
    sign: str = ""


@dataclass(frozen=True)
class PlanetHitArea:
    """Stores interactive hit-test data for one rendered planet badge."""

    planet: PlanetDisplay
    rect: QRectF


@dataclass(frozen=True)
class ChartHeaderData:
    """Presentation metadata shown above the chart."""

    title: str = "North Indian Kundli"
    name: str = ""
    dob: str = ""
    tob: str = ""
    place: str = ""


class NorthIndianChartWidget(QWidget):
    planet_hovered = pyqtSignal(dict)
    planet_clicked = pyqtSignal(dict)
    house_hovered = pyqtSignal(dict)
    house_clicked = pyqtSignal(int)
    hover_cleared = pyqtSignal()

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
    HOUSE_SLOT_BORDER_COLOR = QColor("#E2E8F0")
    HOUSE_SLOT_FILL_COLOR = QColor("#F8FAFC")
    OCCUPIED_HOUSE_BORDER_COLOR = QColor("#CBD5E1")
    OCCUPIED_HOUSE_FILL_COLOR = QColor(241, 245, 249, 220)
    HOVERED_HOUSE_BORDER_COLOR = QColor("#7C3AED")
    HOVERED_HOUSE_FILL_COLOR = QColor(124, 58, 237, 28)
    HOVERED_PLANET_BORDER_COLOR = QColor("#0F172A")
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

    PLANET_COLORS = {
        "As": QColor("#7C3AED"),
        "Su": QColor("#EA580C"),
        "Mo": QColor("#2563EB"),
        "Ma": QColor("#DC2626"),
        "Me": QColor("#059669"),
        "Ju": QColor("#D97706"),
        "Ve": QColor("#DB2777"),
        "Sa": QColor("#475569"),
        "Ra": QColor("#0F766E"),
        "Ke": QColor("#7C2D12"),
    }

    def __init__(self, parent: Optional[QWidget] = None, language_manager: LanguageManager | None = None) -> None:
        super().__init__(parent)
        self.language_manager = language_manager or LanguageManager()
        self.setMinimumSize(360, 360)
        self.setMouseTracking(True)
        self._show_house_labels = True
        self._house_cells: Dict[int, HouseCell] = {}
        self._planets_by_house: Dict[int, List[PlanetDisplay]] = {house: [] for house in range(1, 13)}
        self._header_data = ChartHeaderData()
        self._hovered_house: Optional[int] = None
        self._hovered_planet: Optional[PlanetDisplay] = None
        self._planet_hit_areas: List[PlanetHitArea] = []
        self._insights_by_planet: Dict[str, str] = {}
        self._insights_by_house: Dict[int, str] = {}
        self._default_insight = ""

    def sizeHint(self) -> QSize:
        return QSize(420, 420)

    def _tr(self, key: str) -> str:
        return self.language_manager.get_text(key)

    def set_show_house_labels(self, visible: bool) -> None:
        self._show_house_labels = visible
        self.update()

    def set_header_data(self, header_data: ChartHeaderData) -> None:
        self._header_data = header_data
        self.update()

    def clear_header_data(self) -> None:
        self._header_data = ChartHeaderData()
        self.update()

    def set_insights(
        self,
        *,
        by_planet: Optional[Dict[str, str]] = None,
        by_house: Optional[Dict[int, str]] = None,
        default: str = "",
    ) -> None:
        self._insights_by_planet = {str(key): str(value).strip() for key, value in (by_planet or {}).items() if str(value).strip()}
        self._insights_by_house = {
            int(key): str(value).strip()
            for key, value in (by_house or {}).items()
            if str(value).strip()
        }
        self._default_insight = str(default or "").strip()

    def clear_insights(self) -> None:
        self._insights_by_planet = {}
        self._insights_by_house = {}
        self._default_insight = ""

    def get_house_insight(self, house: int) -> str:
        return self._insight_for_house(house)

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
        self._planet_hit_areas = []
        self._hovered_house = None
        self._hovered_planet = None

        for item in chart_data:
            planet = self._extract_planet_name(item)
            house = self._extract_house_number(item)
            if not planet or house is None or house not in self._planets_by_house:
                continue

            self._planets_by_house[house].append(
                PlanetDisplay(
                    code=self._abbreviate_planet(planet),
                    house=house,
                    name=planet,
                    sign=self._extract_sign(item),
                )
            )

        self.update()

    def clear_chart_data(self) -> None:
        self._planets_by_house = {house: [] for house in range(1, 13)}
        self._planet_hit_areas = []
        self._hovered_house = None
        self._hovered_planet = None
        self.clear_insights()
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
        self._planet_hit_areas = []

        self._draw_chart_frame(painter, chart_rect)

        if self._show_house_labels:
            self._draw_house_labels(painter)

        self._draw_hovered_house_outline(painter)
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
        
        # 1. Subtle drop shadow to elevate the chart
        shadow_rect = QRectF(
            (self.MARGIN / 2) + 2,
            (self.MARGIN / 2) + 4,
            self.width() - self.MARGIN,
            self.height() - self.MARGIN,
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 10)) # Very light shadow
        painter.drawRoundedRect(shadow_rect, 12.0, 12.0)

        # 2. Main card background
        painter.setPen(QPen(self.CARD_BORDER_COLOR, 1.0))
        painter.setBrush(QColor("#FFFFFF")) # Pure white card contrast against outer cream background
        frame_rect = QRectF(
            self.MARGIN / 2,
            self.MARGIN / 2,
            self.width() - self.MARGIN,
            self.height() - self.MARGIN,
        )
        painter.drawRoundedRect(frame_rect, 12.0, 12.0)
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
            f"{self._tr('ui.name')}: {self._header_data.name}" if self._header_data.name else "",
            f"{self._tr('ui.date_of_birth')}: {self._header_data.dob}" if self._header_data.dob else "",
            f"{self._tr('ui.time_of_birth')}: {self._header_data.tob}" if self._header_data.tob else "",
            f"{self._tr('ui.place')}: {self._header_data.place}" if self._header_data.place else "",
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

        for house_number, planets in self._planets_by_house.items():
            if not planets:
                continue

            cell = self._house_cells.get(house_number)
            if cell is None:
                continue

            planet_slots = self._build_planet_layout(cell.content_rect, len(planets))
            painter.setFont(self._planet_font_for_count(len(planets), cell.content_rect))
            self._draw_house_focus_background(painter, cell.content_rect)

            for planet, slot_rect in zip(planets, planet_slots):
                self._draw_planet_badge(painter, planet, slot_rect)
                self._planet_hit_areas.append(PlanetHitArea(planet=planet, rect=QRectF(slot_rect)))
                painter.setPen(QPen(self._planet_text_color(planet.code), 1.0))
                painter.drawText(
                    self._badge_text_rect(slot_rect),
                    Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter,
                    planet.code,
                )

        painter.restore()

    def _draw_hovered_house_outline(self, painter: QPainter) -> None:
        if self._hovered_house is None:
            return

        hovered_cell = self._house_cells.get(self._hovered_house)
        if hovered_cell is None:
            return

        if self._planets_by_house.get(self._hovered_house):
            return

        focus_rect = QRectF(hovered_cell.content_rect)
        focus_rect.adjust(-4.0, -3.0, 4.0, 3.0)

        painter.save()
        painter.setPen(QPen(self.HOVERED_HOUSE_BORDER_COLOR, 2.0))
        painter.setBrush(self.HOVERED_HOUSE_FILL_COLOR)
        painter.drawRoundedRect(focus_rect, 8.0, 8.0)
        painter.restore()

    def _draw_house_focus_background(self, painter: QPainter, content_rect: QRectF) -> None:
        focus_rect = QRectF(content_rect)
        focus_rect.adjust(-4.0, -3.0, 4.0, 3.0)

        painter.save()
        house_number = self._house_for_rect(content_rect)
        is_hovered = house_number is not None and house_number == self._hovered_house
        
        border_color = self.HOVERED_HOUSE_BORDER_COLOR if is_hovered else self.OCCUPIED_HOUSE_BORDER_COLOR
        fill_color = self.HOVERED_HOUSE_FILL_COLOR if is_hovered else self.OCCUPIED_HOUSE_FILL_COLOR
        
        painter.setPen(QPen(border_color, 2.0 if is_hovered else 1.0))
        painter.setBrush(fill_color)
        painter.drawRoundedRect(focus_rect, 8.0, 8.0)
        painter.restore()

    def _draw_planet_badge(self, painter: QPainter, planet: PlanetDisplay, slot_rect: QRectF) -> None:
        badge_rect = QRectF(slot_rect)
        badge_rect.adjust(1.5, 1.5, -1.5, -1.5)

        painter.save()
        
        # Draw micro-shadow for planet badges
        shadow_rect = QRectF(badge_rect)
        shadow_rect.translate(0, 1.5)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 15))
        painter.drawRoundedRect(shadow_rect, 6.0, 6.0)
        
        is_hovered = self._hovered_planet == planet
        border_color = self.HOVERED_PLANET_BORDER_COLOR if is_hovered else self.HOUSE_SLOT_BORDER_COLOR
        border_width = 1.5 if is_hovered else 1.0
        painter.setPen(QPen(border_color, border_width))
        painter.setBrush(self._planet_badge_fill(planet.code))
        painter.drawRoundedRect(badge_rect, 6.0, 6.0)
        painter.restore()

    def _badge_text_rect(self, slot_rect: QRectF) -> QRectF:
        text_rect = QRectF(slot_rect)
        text_rect.adjust(2.0, 1.0, -2.0, -1.0)
        return text_rect

    def _planet_badge_fill(self, planet_code: str) -> QColor:
        base = QColor(self.PLANET_COLORS.get(planet_code, self.HOUSE_SLOT_FILL_COLOR))
        fill = QColor(base)
        fill.setAlpha(52)
        return fill

    def _planet_text_color(self, planet_code: str) -> QColor:
        return QColor(self.PLANET_COLORS.get(planet_code, self.PLANET_TEXT_COLOR))

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        hovered_planet = self._planet_at_position(event.position().toPoint())
        hovered_house = hovered_planet.house if hovered_planet else self._house_at_position(event.position().toPoint())

        if hovered_planet != self._hovered_planet or hovered_house != self._hovered_house:
            self._hovered_planet = hovered_planet
            self._hovered_house = hovered_house
            self.update()

        if hovered_planet:
            QToolTip.showText(event.globalPosition().toPoint(), self._planet_tooltip_text(hovered_planet), self)
            self.planet_hovered.emit(
                {
                    "planet": hovered_planet.name,
                    "code": hovered_planet.code,
                    "house": hovered_planet.house,
                    "sign": hovered_planet.sign,
                    "insight": self._insight_for_planet(hovered_planet),
                }
            )
        elif hovered_house is not None:
            QToolTip.showText(event.globalPosition().toPoint(), self._house_tooltip_text(hovered_house), self)
            self.house_hovered.emit(
                {
                    "house": hovered_house,
                    "insight": self._insight_for_house(hovered_house),
                }
            )
        else:
            QToolTip.hideText()
            self.hover_cleared.emit()

        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered_house = None
        self._hovered_planet = None
        QToolTip.hideText()
        self.hover_cleared.emit()
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            clicked_planet = self._planet_at_position(event.position().toPoint())
            if clicked_planet:
                self.planet_clicked.emit(
                    {
                        "planet": clicked_planet.name,
                        "code": clicked_planet.code,
                        "house": clicked_planet.house,
                        "sign": clicked_planet.sign,
                        "insight": self._insight_for_planet(clicked_planet),
                    }
                )
                event.accept()
                return

            clicked_house = self._house_at_position(event.position().toPoint())
            if clicked_house is not None:
                self.house_clicked.emit(clicked_house)
                event.accept()
                return

        super().mousePressEvent(event)

    def _planet_at_position(self, point: QPoint) -> Optional[PlanetDisplay]:
        for hit_area in reversed(self._planet_hit_areas):
            if hit_area.rect.contains(QPointF(point)):
                return hit_area.planet
        return None

    def _house_at_position(self, point: QPoint) -> Optional[int]:
        pointf = QPointF(point)
        for house_number, cell in self._house_cells.items():
            focus_rect = QRectF(cell.content_rect)
            focus_rect.adjust(-4.0, -3.0, 4.0, 3.0)
            if focus_rect.contains(pointf):
                return house_number
        return None

    def _house_for_rect(self, content_rect: QRectF) -> Optional[int]:
        for house_number, cell in self._house_cells.items():
            if cell.content_rect == content_rect:
                return house_number
        return None

    def _planet_tooltip_text(self, planet: PlanetDisplay) -> str:
        text = f"<b><span style='font-size:14pt;'>{self._localized_planet_name(planet.name or planet.code)}</span></b><br/>"
        text += f"{self._tr('chart.house')}: {planet.house}"
        if planet.sign:
            text += f"<br/>{self._tr('chart.sign')}: {planet.sign}"
        
        insight = self._insight_for_planet(planet)
        if insight:
            text += f"<hr/><i style='color: #475569;'>{insight}</i>"
            
        return f"<div style='padding: 4px;'>{text}</div>"

    def _house_tooltip_text(self, house: int) -> str:
        text = f"<b><span style='font-size:14pt;'>{self._tr('chart.house')} {house}</span></b>"
        
        insight = self._insight_for_house(house)
        if insight:
            text += f"<hr/><i style='color: #475569;'>{insight}</i>"
            
        return f"<div style='padding: 4px;'>{text}</div>"

    def _insight_for_planet(self, planet: PlanetDisplay) -> str:
        key = self._planet_insight_key(planet.name or planet.code, planet.house)
        return self._insights_by_planet.get(key) or self._insights_by_house.get(planet.house, "") or self._default_insight

    def _insight_for_house(self, house: int) -> str:
        return self._insights_by_house.get(house, "") or self._default_insight

    def _planet_insight_key(self, planet_name: str, house: int) -> str:
        normalized_planet = re.sub(r"\s+", " ", str(planet_name or "").strip().lower())
        return f"{normalized_planet}|{int(house)}"

    def _build_planet_layout(self, content_rect: QRectF, planet_count: int) -> List[QRectF]:
        """
        Distributes planets inside a house cell radially to prevent overlap 
        and fit organically inside diamond/triangular chart houses.
        """
        if planet_count <= 0:
            return []

        if planet_count == 1:
            return [content_rect]

        # Calculate a safe radius for the badges to orbit the center
        usable_width = content_rect.width() * 0.8
        usable_height = content_rect.height() * 0.8
        
        # Max radius shrinks slightly as more planets are added to avoid edge clipping
        radius_factor = 0.35 if planet_count < 5 else 0.42
        rx = usable_width * radius_factor
        ry = usable_height * radius_factor

        cx = content_rect.center().x()
        cy = content_rect.center().y()

        # Dynamic badge size based on planet count
        badge_side = min(usable_width, usable_height) / (1.5 + (planet_count * 0.2))
        
        layout_rects: List[QRectF] = []
        
        for i in range(planet_count):
            # Calculate angle in radians. Start at -90 deg (top) and distribute evenly
            angle = math.radians(-90 + (i * (360 / planet_count)))
            
            x = cx + (rx * math.cos(angle)) - (badge_side / 2)
            y = cy + (ry * math.sin(angle)) - (badge_side / 2)
            
            layout_rects.append(QRectF(x, y, badge_side, badge_side))

        return layout_rects

    def _planet_font_for_count(self, planet_count: int, content_rect: QRectF) -> QFont:
        # Adjusted scaling to match the new radial badge sizes dynamically
        base_size = min(content_rect.width(), content_rect.height())
        if planet_count <= 1:
            size = max(10, int(base_size * 0.22))
        elif planet_count == 2:
            size = max(9, int(base_size * 0.18))
        elif planet_count <= 4:
            size = max(8, int(base_size * 0.15))
        else:
            size = max(7, int(base_size * 0.12))

        return QFont("Segoe UI", size, QFont.Weight.Bold)

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

    def _extract_sign(self, item: Union[ChartData, dict]) -> str:
        if isinstance(item, ChartData):
            return str(item.sign or "").strip()
        if isinstance(item, dict):
            return str(item.get("Sign") or item.get("sign") or "").strip()
        return ""

    def _abbreviate_planet(self, planet_name: str) -> str:
        normalized = planet_name.strip()
        if not normalized:
            return ""
        return self.PLANET_ABBREVIATIONS.get(normalized, normalized[:2].title())

    def _localized_planet_name(self, planet_name: str) -> str:
        normalized = re.sub(r"\s+", "_", str(planet_name or "").strip().lower())
        return self._tr(f"planet.{normalized}")


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
                {"Planet": "Venus", "House": 1},
                {"Planet": "Saturn", "House": 1},
                {"Planet": "Moon", "House": 4},
                {"Planet": "Mars", "House": 7},
                {"Planet": "Jupiter", "House": 9},
                {"Planet": "Rahu", "House": 11},
                {"Planet": "Ketu", "House": 5},
                {"Planet": "Sun", "House": 10},
                {"Planet": "Moon", "House": 10},
                {"Planet": "Mercury", "House": 10},
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
