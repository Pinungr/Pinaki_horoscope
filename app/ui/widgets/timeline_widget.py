from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List

from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)
from app.ui.theme import set_button_icon


class TimelineBarItem(QGraphicsRectItem):
    """Clickable graphics item that delegates dasha selection back to the widget."""

    def __init__(self, rect: QRectF, payload: Dict[str, Any], click_handler, parent=None):
        super().__init__(rect, parent)
        self._payload = payload
        self._click_handler = click_handler
        self._default_pen = QPen(QColor("#64748b"))
        self._default_brush = QBrush(QColor("#cbd5e1"))
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if callable(self._click_handler):
            self._click_handler(self, self._payload)
        super().mousePressEvent(event)

    def remember_style(self, pen: QPen, brush: QBrush) -> None:
        """Stores the base styling so selection can be toggled safely."""
        self._default_pen = QPen(pen)
        self._default_brush = QBrush(brush)

    def set_selected(self, selected: bool) -> None:
        """Applies a stronger outline to the selected dasha bar."""
        if selected:
            selected_pen = QPen(QColor("#0f172a"))
            selected_pen.setWidth(max(self._default_pen.width() + 1, 3))
            self.setPen(selected_pen)

            selected_brush = QBrush(self._default_brush)
            selected_color = QColor(selected_brush.color())
            selected_color.setAlpha(min(selected_color.alpha() + 30, 255))
            selected_brush.setColor(selected_color)
            self.setBrush(selected_brush)
            return

        self.setPen(QPen(self._default_pen))
        self.setBrush(QBrush(self._default_brush))


class TimelineWidget(QGraphicsView):
    """
    Reusable scrollable timeline widget for rendering Dasha periods.

    Expected input format:
    {
        "timeline": [
            {
                "planet": "Saturn",
                "start": "2025-01-01",
                "end": "2044-01-01",
                "events": [...]
            }
        ]
    }
    """

    LEFT_MARGIN = 24
    TOP_MARGIN = 20
    RIGHT_MARGIN = 40
    BOTTOM_MARGIN = 24
    CONTROL_HEIGHT = 34
    ROW_HEIGHT = 72
    BAR_HEIGHT = 24
    MIN_BAR_WIDTH = 120
    PIXELS_PER_DAY = 0.18
    MIN_ZOOM_PERCENT = 70
    MAX_ZOOM_PERCENT = 220
    ZOOM_STEP = 15
    EVENT_COLORS = {
        "career": QColor("#3b82f6"),
        "marriage": QColor("#ec4899"),
        "finance": QColor("#22c55e"),
        "health": QColor("#f59e0b"),
        "general": QColor("#94a3b8"),
    }
    CONFIDENCE_ORDER = {
        "low": 0,
        "medium": 1,
        "high": 2,
    }
    period_selected = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self._all_timeline_rows: List[Dict[str, Any]] = []
        self._timeline_rows: List[Dict[str, Any]] = []
        self._timeline_mode = "dasha"
        self._active_filter = "all"
        self._zoom_percent = 100
        self._selected_bar_item: TimelineBarItem | None = None
        self._filter_buttons: Dict[str, QPushButton] = {}
        self._zoom_label: QLabel | None = None
        self._content_top = self.TOP_MARGIN + self.CONTROL_HEIGHT + 20

        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setMinimumHeight(280)
        self.setStyleSheet("background: #fbfbfd; border: 1px solid #d9dce3;")
        self._controls_widget = self._build_controls_widget()

        self.set_timeline_data({"timeline": []})

    def set_timeline_data(self, data: Dict[str, Any]) -> None:
        """Loads timeline JSON data and redraws the scene."""
        timeline = data.get("timeline", []) if isinstance(data, dict) else []
        self._all_timeline_rows = [row for row in timeline if isinstance(row, dict)]
        self._timeline_mode = self._detect_timeline_mode(data, self._all_timeline_rows)
        self._apply_filter()

    def clear_timeline(self) -> None:
        """Clears all rendered timeline content."""
        self.set_timeline_data({"timeline": []})

    def set_event_filter(self, filter_name: str) -> None:
        """Applies a category filter such as all, career, marriage, or finance."""
        normalized = str(filter_name or "all").strip().lower() or "all"
        if normalized not in {"all", "career", "marriage", "finance", "health"}:
            normalized = "all"
        self._active_filter = normalized
        self._apply_filter()

    def set_zoom_percent(self, value: int) -> None:
        """Adjusts horizontal zoom while preserving vertical readability."""
        clamped = max(self.MIN_ZOOM_PERCENT, min(self.MAX_ZOOM_PERCENT, int(value)))
        self._zoom_percent = clamped
        self.resetTransform()
        self.scale(clamped / 100.0, 1.0)
        self._refresh_control_states()

    def reset_zoom(self) -> None:
        """Restores the default zoom."""
        self.set_zoom_percent(100)

    def wheelEvent(self, event) -> None:
        """Supports Ctrl plus mouse wheel zooming while keeping scroll behavior intact."""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            step = self.ZOOM_STEP if delta > 0 else -self.ZOOM_STEP
            self.set_zoom_percent(self._zoom_percent + step)
            event.accept()
            return
        super().wheelEvent(event)

    def resizeEvent(self, event) -> None:
        """Keeps the overlay controls anchored to the top-left of the viewport."""
        super().resizeEvent(event)
        self._position_controls()

    def _redraw_scene(self) -> None:
        self._scene.clear()
        self._selected_bar_item = None
        self._position_controls()

        if self._timeline_mode == "forecast":
            self._redraw_forecast_scene()
            return

        if not self._timeline_rows:
            empty_text = self._scene.addText(self._empty_state_text())
            empty_text.setDefaultTextColor(QColor("#6b7280"))
            empty_text.setPos(self.LEFT_MARGIN, self._content_top + 8)
            self._scene.setSceneRect(QRectF(0, 0, 760, self._content_top + 120))
            self._refresh_control_states()
            return

        parsed_rows = []
        for row in self._timeline_rows:
            start_date = self._parse_date(row.get("start"))
            end_date = self._parse_date(row.get("end"))
            if not start_date or not end_date:
                continue
            if end_date < start_date:
                start_date, end_date = end_date, start_date

            parsed_rows.append(
                {
                    **row,
                    "_start_date": start_date,
                    "_end_date": end_date,
                }
            )

        if not parsed_rows:
            invalid_text = self._scene.addText("Timeline data has no valid date ranges.")
            invalid_text.setDefaultTextColor(QColor("#b45309"))
            invalid_text.setPos(self.LEFT_MARGIN, self._content_top + 8)
            self._scene.setSceneRect(QRectF(0, 0, 760, self._content_top + 120))
            self._refresh_control_states()
            return

        parsed_rows.sort(key=lambda row: row["_start_date"])
        timeline_start = min(row["_start_date"] for row in parsed_rows)
        timeline_end = max(row["_end_date"] for row in parsed_rows)
        total_days = max((timeline_end - timeline_start).days, 1)
        timeline_width = max(
            self.MIN_BAR_WIDTH * len(parsed_rows),
            total_days * self.PIXELS_PER_DAY,
        )

        title_item = self._scene.addText("Life Timeline")
        title_item.setDefaultTextColor(QColor("#111827"))
        title_item.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title_item.setPos(self.LEFT_MARGIN, self._content_top)

        self._draw_legend(title_item.boundingRect().width() + self.LEFT_MARGIN + 24, self._content_top + 2)

        for index, row in enumerate(parsed_rows):
            self._draw_timeline_row(
                row=row,
                row_index=index,
                timeline_start=timeline_start,
                timeline_width=timeline_width,
                total_days=total_days,
            )

        scene_height = self._content_top + 24 + (len(parsed_rows) * self.ROW_HEIGHT) + self.BOTTOM_MARGIN
        scene_width = self.LEFT_MARGIN + timeline_width + self.RIGHT_MARGIN
        self._scene.setSceneRect(QRectF(0, 0, scene_width, scene_height))
        self._refresh_control_states()

    def _redraw_forecast_scene(self) -> None:
        """Renders forecast rows as year-wise cards."""
        rows = [row for row in self._timeline_rows if isinstance(row, dict)]
        if not rows:
            empty_text = self._scene.addText(self._empty_state_text())
            empty_text.setDefaultTextColor(QColor("#6b7280"))
            empty_text.setPos(self.LEFT_MARGIN, self._content_top + 8)
            self._scene.setSceneRect(QRectF(0, 0, 760, self._content_top + 120))
            self._refresh_control_states()
            return

        rows.sort(
            key=lambda row: (
                self._parse_date(row.get("start")) or date.max,
                -self._safe_int(row.get("confidence")),
            )
        )

        title_item = self._scene.addText("Timeline Forecast")
        title_item.setDefaultTextColor(QColor("#111827"))
        title_item.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title_item.setPos(self.LEFT_MARGIN, self._content_top)

        row_top = self._content_top + 38
        card_width = max(self.viewport().width() - (self.LEFT_MARGIN + self.RIGHT_MARGIN + 12), 520)
        card_height = 96
        gap = 12

        for index, row in enumerate(rows):
            y = row_top + (index * (card_height + gap))
            self._draw_forecast_card(row, y, card_width, card_height)

        scene_height = row_top + (len(rows) * (card_height + gap)) + self.BOTTOM_MARGIN
        scene_width = self.LEFT_MARGIN + card_width + self.RIGHT_MARGIN
        self._scene.setSceneRect(QRectF(0, 0, scene_width, scene_height))
        self._refresh_control_states()

    def _draw_forecast_card(self, row: Dict[str, Any], y: float, width: float, height: float) -> None:
        area = self._normalize_event_type(row.get("area", "general"))
        color = self._color_for_event(area)
        activation_code = str(row.get("activation_label", "dormant")).strip().lower() or "dormant"
        activation_trend = str(row.get("activation_trend", "stable")).strip().lower() or "stable"
        transition_text = self._activation_transition_text(activation_code, activation_trend)
        activation_text = self._activation_label_text(activation_code)
        activation_color = self._activation_color(activation_code)
        transit_text = self._transit_label(row.get("transit_support_state", "neutral"))
        concordance_text = str(row.get("agreement_level", "medium")).strip().lower() or "medium"
        period = str(row.get("period", "")).strip() or self._period_from_dates(row.get("start"), row.get("end"))
        event = str(row.get("event", "")).strip() or "Notable life developments"
        yoga = str(row.get("yoga", "")).strip()
        reasoning_link = str(row.get("reasoning_link", "")).strip()
        confidence_score = self._safe_int(row.get("confidence"))

        card_rect = QRectF(self.LEFT_MARGIN, y, width, height)
        border_pen = QPen(color.darker(125))
        border_pen.setWidth(3 if transition_text else 2)
        self._scene.addRect(card_rect, border_pen, QBrush(QColor("#ffffff")))

        badge_rect = QRectF(self.LEFT_MARGIN + 10, y + 10, 114, 24)
        badge_fill = QColor(color)
        badge_fill.setAlpha(220)
        self._scene.addRect(badge_rect, QPen(Qt.PenStyle.NoPen), QBrush(badge_fill))

        badge_text = QGraphicsSimpleTextItem(period)
        badge_text.setBrush(QBrush(QColor("#ffffff")))
        badge_text.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        badge_bounds = badge_text.boundingRect()
        badge_text.setPos(
            badge_rect.x() + ((badge_rect.width() - badge_bounds.width()) / 2),
            badge_rect.y() + ((badge_rect.height() - badge_bounds.height()) / 2) - 1,
        )
        self._scene.addItem(badge_text)

        headline = QGraphicsSimpleTextItem(f"{area.title()} | Confidence {confidence_score}")
        headline.setBrush(QBrush(QColor("#0f172a")))
        headline.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        headline.setPos(self.LEFT_MARGIN + 132, y + 12)
        self._scene.addItem(headline)

        activation_badge_rect = QRectF(self.LEFT_MARGIN + width - 178, y + 10, 164, 22)
        activation_fill = QColor(activation_color)
        activation_fill.setAlpha(220)
        self._scene.addRect(activation_badge_rect, QPen(Qt.PenStyle.NoPen), QBrush(activation_fill))

        activation_badge_text = QGraphicsSimpleTextItem(f"Activation: {activation_text}")
        activation_badge_text.setBrush(QBrush(QColor("#ffffff")))
        activation_badge_text.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        activation_bounds = activation_badge_text.boundingRect()
        activation_badge_text.setPos(
            activation_badge_rect.x() + ((activation_badge_rect.width() - activation_bounds.width()) / 2),
            activation_badge_rect.y() + ((activation_badge_rect.height() - activation_bounds.height()) / 2) - 1,
        )
        self._scene.addItem(activation_badge_text)

        signal_line = f"Transit: {transit_text} | Concordance: {concordance_text.title()}"
        signal_item = QGraphicsSimpleTextItem(signal_line)
        signal_item.setBrush(QBrush(QColor("#475569")))
        signal_item.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        signal_item.setPos(self.LEFT_MARGIN + 132, y + 32)
        self._scene.addItem(signal_item)

        detail_parts = [event]
        if yoga:
            detail_parts.append(f"Yoga: {yoga}")
        if reasoning_link:
            detail_parts.append(reasoning_link)
        detail_text = " | ".join(part for part in detail_parts if part)
        detail_item = QGraphicsSimpleTextItem(detail_text[:180] + ("..." if len(detail_text) > 180 else ""))
        detail_item.setBrush(QBrush(QColor("#334155")))
        detail_item.setFont(QFont("Segoe UI", 8))
        detail_item.setPos(self.LEFT_MARGIN + 14, y + 54)
        self._scene.addItem(detail_item)

        if transition_text:
            transition_item = QGraphicsSimpleTextItem(transition_text)
            transition_item.setBrush(QBrush(QColor("#b45309")))
            transition_item.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            transition_item.setPos(self.LEFT_MARGIN + 14, y + 32)
            self._scene.addItem(transition_item)

        payload = {
            "planet": area.title(),
            "start": str(row.get("start", "")),
            "end": str(row.get("end", "")),
            "activation_label": activation_code,
            "activation_trend": activation_trend,
            "events": [
                {
                    "type": area,
                    "confidence": "high" if confidence_score >= 80 else "medium",
                    "summary": event,
                }
            ],
        }
        click_layer = TimelineBarItem(card_rect, payload, self._handle_period_click)
        click_layer.setPen(QPen(Qt.PenStyle.NoPen))
        click_layer.setBrush(QBrush(QColor(0, 0, 0, 0)))
        click_layer.setToolTip(self._build_dasha_tooltip(payload))
        self._scene.addItem(click_layer)

    def _draw_timeline_row(
        self,
        row: Dict[str, Any],
        row_index: int,
        timeline_start: date,
        timeline_width: float,
        total_days: int,
    ) -> None:
        start_date = row["_start_date"]
        end_date = row["_end_date"]
        duration_days = max((end_date - start_date).days, 1)
        events = self._normalize_events(row.get("events", []))
        primary_event = self._select_primary_event(events)
        primary_color = self._color_for_event(primary_event.get("type", "general"))
        confidence = self._normalize_confidence(primary_event.get("confidence"))
        emphasis = self._style_for_confidence(confidence)

        row_top = self._content_top + 38 + (row_index * self.ROW_HEIGHT)
        start_offset = (start_date - timeline_start).days
        bar_x = self.LEFT_MARGIN + ((start_offset / total_days) * timeline_width)
        bar_width = max((duration_days / total_days) * timeline_width, self.MIN_BAR_WIDTH)
        bar_height = self.BAR_HEIGHT + emphasis["height_delta"]
        bar_y = row_top + 14 - (emphasis["height_delta"] / 2)

        label_text = str(row.get("planet", "Unknown"))
        date_text = f"{start_date.isoformat()}  ->  {end_date.isoformat()}"
        event_text = self._format_event_summary(events)

        label_item = QGraphicsSimpleTextItem(label_text)
        label_item.setBrush(QBrush(QColor("#1f2937")))
        label_item.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        label_item.setPos(bar_x, row_top - 2)
        self._scene.addItem(label_item)

        track_rect = QRectF(bar_x, bar_y, bar_width, bar_height)
        track_pen = QPen(QColor("#cbd5e1"))
        track_pen.setWidth(1)
        self._scene.addRect(
            track_rect,
            track_pen,
            QBrush(QColor("#f1f5f9")),
        )

        bar_rect = QRectF(bar_x + 1, bar_y + 1, max(bar_width - 2, 6), max(bar_height - 2, 6))
        bar_pen = QPen(primary_color.darker(130))
        bar_pen.setWidth(emphasis["border_width"])
        fill_color = QColor(primary_color)
        fill_color.setAlpha(emphasis["fill_alpha"])
        payload = self._build_period_payload(row, events)
        bar_item = TimelineBarItem(bar_rect, payload, self._handle_period_click)
        bar_item.setPen(bar_pen)
        bar_item.setBrush(QBrush(fill_color))
        bar_item.remember_style(bar_pen, QBrush(fill_color))
        bar_item.setToolTip(self._build_dasha_tooltip(payload))
        self._scene.addItem(bar_item)

        self._draw_event_ribbon(events, bar_rect)
        self._draw_event_markers(events, bar_rect)

        date_item = QGraphicsSimpleTextItem(date_text)
        date_item.setBrush(QBrush(QColor("#475569")))
        date_item.setFont(QFont("Segoe UI", 8))
        date_item.setPos(bar_x, bar_y + bar_height + 6)
        self._scene.addItem(date_item)

        if event_text:
            event_item = QGraphicsSimpleTextItem(event_text)
            event_item.setBrush(QBrush(QColor("#334155")))
            event_item.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
            event_item.setPos(bar_x + 8, bar_y + max((bar_height - 14) / 2, 2))
            event_item.setToolTip(self._build_dasha_tooltip(payload))
            self._scene.addItem(event_item)

    @staticmethod
    def _parse_date(value: Any) -> date | None:
        """Parses YYYY-MM-DD strings into date objects."""
        if not value:
            return None
        if isinstance(value, date):
            return value
        try:
            return datetime.strptime(str(value), "%Y-%m-%d").date()
        except ValueError:
            return None

    def _build_controls_widget(self) -> QWidget:
        """Builds fixed overlay controls for timeline filtering and zoom."""
        controls = QWidget(self.viewport())
        controls.setStyleSheet(
            """
            QWidget {
                background: #f8fafc;
                border: 1px solid #d8dee9;
                border-radius: 10px;
            }
            QLabel {
                color: #334155;
                font-weight: 600;
            }
            QPushButton {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 7px;
                color: #334155;
                padding: 5px 10px;
            }
            QPushButton:checked {
                background: #e0f2fe;
                border: 1px solid #38bdf8;
                color: #0f172a;
            }
            """
        )
        controls.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout()
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Filter"))
        self._filter_buttons = {}
        for filter_name, label in (
            ("all", "All"),
            ("career", "Career"),
            ("marriage", "Marriage"),
            ("finance", "Finance"),
            ("health", "Health"),
        ):
            button = QPushButton(label)
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, value=filter_name: self.set_event_filter(value))
            layout.addWidget(button)
            self._filter_buttons[filter_name] = button

        zoom_out_button = QPushButton("Zoom -")
        zoom_out_button.clicked.connect(lambda: self.set_zoom_percent(self._zoom_percent - self.ZOOM_STEP))
        set_button_icon(zoom_out_button, "zoom_out")
        layout.addWidget(zoom_out_button)

        zoom_reset_button = QPushButton("Reset")
        zoom_reset_button.clicked.connect(self.reset_zoom)
        set_button_icon(zoom_reset_button, "reset")
        layout.addWidget(zoom_reset_button)

        zoom_in_button = QPushButton("Zoom +")
        zoom_in_button.clicked.connect(lambda: self.set_zoom_percent(self._zoom_percent + self.ZOOM_STEP))
        set_button_icon(zoom_in_button, "zoom_in")
        layout.addWidget(zoom_in_button)

        self._zoom_label = QLabel()
        layout.addWidget(self._zoom_label)
        layout.addStretch(1)

        controls.setLayout(layout)
        controls.adjustSize()
        controls.show()
        self._position_controls()
        return controls

    def _position_controls(self) -> None:
        """Pins the controls overlay inside the viewport instead of the zoomable scene."""
        if not hasattr(self, "_controls_widget") or self._controls_widget is None:
            return
        self._controls_widget.adjustSize()
        self._controls_widget.move(self.LEFT_MARGIN, self.TOP_MARGIN)
        self._controls_widget.raise_()

    def _draw_legend(self, x: float, y: float) -> None:
        """Draws a small color legend for event types and confidence emphasis."""
        legend_entries = [
            ("Career", self.EVENT_COLORS["career"]),
            ("Marriage", self.EVENT_COLORS["marriage"]),
            ("Finance", self.EVENT_COLORS["finance"]),
            ("Health", self.EVENT_COLORS["health"]),
        ]

        cursor_x = x
        for label, color in legend_entries:
            chip = QRectF(cursor_x, y + 3, 12, 12)
            self._scene.addRect(chip, QPen(color.darker(125)), QBrush(color))

            text_item = QGraphicsSimpleTextItem(label)
            text_item.setBrush(QBrush(QColor("#475569")))
            text_item.setFont(QFont("Segoe UI", 8))
            text_item.setPos(cursor_x + 18, y)
            self._scene.addItem(text_item)

            cursor_x += 82

        hint_item = QGraphicsSimpleTextItem("High confidence = bolder bar")
        hint_item.setBrush(QBrush(QColor("#64748b")))
        hint_item.setFont(QFont("Segoe UI", 8))
        hint_item.setPos(cursor_x + 4, y)
        self._scene.addItem(hint_item)

    def _draw_event_ribbon(self, events: List[Dict[str, str]], bar_rect: QRectF) -> None:
        """Draws a slim multi-color ribbon showing all event types on the dasha bar."""
        if not events:
            return

        ribbon_height = min(6.0, bar_rect.height() / 3)
        segment_width = bar_rect.width() / max(len(events), 1)
        for index, event in enumerate(events):
            color = QColor(self._color_for_event(event.get("type", "general")))
            color.setAlpha(235)
            segment_rect = QRectF(
                bar_rect.x() + (index * segment_width),
                bar_rect.y(),
                segment_width,
                ribbon_height,
            )
            self._scene.addRect(segment_rect, QPen(Qt.PenStyle.NoPen), QBrush(color))

    def _draw_event_markers(self, events: List[Dict[str, str]], bar_rect: QRectF) -> None:
        """Draws event markers inside the dasha bar with hover tooltips."""
        if not events:
            return

        visible_events = events[:4]
        gap = 6.0
        marker_sizes = [
            self._marker_size_for_confidence(self._normalize_confidence(event.get("confidence")))
            for event in visible_events
        ]
        total_marker_width = sum(marker_sizes) + (gap * max(len(marker_sizes) - 1, 0))
        start_x = max(bar_rect.x() + 10, bar_rect.right() - total_marker_width - 10)

        for index, event in enumerate(visible_events):
            confidence = self._normalize_confidence(event.get("confidence"))
            marker_size = marker_sizes[index]
            marker_x = start_x + sum(marker_sizes[:index]) + (gap * index)
            marker_y = bar_rect.y() + ((bar_rect.height() - marker_size) / 2)

            marker_color = QColor(self._color_for_event(event.get("type", "general")))
            marker_fill = QColor(marker_color)
            marker_fill.setAlpha(245 if confidence == "high" else 210 if confidence == "medium" else 160)

            marker_pen = QPen(marker_color.darker(150))
            marker_pen.setWidth(2 if confidence == "high" else 1)
            marker_item = self._scene.addEllipse(
                marker_x,
                marker_y,
                marker_size,
                marker_size,
                marker_pen,
                QBrush(marker_fill),
            )
            marker_item.setToolTip(self._tooltip_for_event(event))
            marker_item.setCursor(Qt.CursorShape.PointingHandCursor)

            marker_label = QGraphicsSimpleTextItem(self._marker_label_for_event(event.get("type", "general")))
            marker_label.setBrush(QBrush(QColor("#ffffff")))
            marker_label.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
            marker_rect = marker_label.boundingRect()
            marker_label.setPos(
                marker_x + ((marker_size - marker_rect.width()) / 2),
                marker_y + ((marker_size - marker_rect.height()) / 2) - 1,
            )
            marker_label.setToolTip(self._tooltip_for_event(event))
            self._scene.addItem(marker_label)

    def _build_period_payload(self, row: Dict[str, Any], events: List[Dict[str, str]]) -> Dict[str, Any]:
        """Builds the reusable period payload emitted on dasha click."""
        return {
            "planet": str(row.get("planet", "Unknown")),
            "start": row.get("start", ""),
            "end": row.get("end", ""),
            "events": [
                {
                    "type": event.get("type", "general"),
                    "confidence": event.get("confidence", "medium"),
                    "summary": event.get("summary", ""),
                }
                for event in events
            ],
        }

    def _build_dasha_tooltip(self, payload: Dict[str, Any]) -> str:
        """Formats hover text for an entire dasha bar."""
        lines = [
            f"{payload.get('planet', 'Unknown')} Dasha",
            f"{payload.get('start', '')} to {payload.get('end', '')}",
        ]
        for event in payload.get("events", []):
            event_type = self._normalize_event_type(event.get("type", "general")).title()
            confidence = self._normalize_confidence(event.get("confidence", "medium")).title()
            summary = str(event.get("summary", "")).strip()
            if summary:
                lines.append(f"{event_type} ({confidence}): {summary}")
            else:
                lines.append(f"{event_type} ({confidence})")
        return "\n".join(lines)

    def _handle_period_click(self, item: TimelineBarItem, payload: Dict[str, Any]) -> None:
        """Highlights the selected bar and emits the payload for controller handling."""
        if self._selected_bar_item is not None and self._selected_bar_item is not item:
            self._selected_bar_item.set_selected(False)

        self._selected_bar_item = item
        self._selected_bar_item.set_selected(True)
        self.centerOn(item)
        self.period_selected.emit(payload)

    def _apply_filter(self) -> None:
        """Rebuilds the visible rows based on the active timeline filter."""
        if self._active_filter == "all":
            self._timeline_rows = list(self._all_timeline_rows)
        else:
            self._timeline_rows = [
                row for row in self._all_timeline_rows if self._row_matches_filter(row, self._active_filter)
            ]
        self._redraw_scene()

    def _row_matches_filter(self, row: Dict[str, Any], filter_name: str) -> bool:
        """Checks whether a dasha period contains the requested event category."""
        if self._timeline_mode == "forecast":
            return self._normalize_event_type(row.get("area", "general")) == filter_name

        for event in self._normalize_events(row.get("events", [])):
            if self._normalize_event_type(event.get("type")) == filter_name:
                return True
        return False

    def _refresh_control_states(self) -> None:
        """Keeps embedded control states aligned after redraws and zoom changes."""
        for filter_name, button in self._filter_buttons.items():
            button.setChecked(filter_name == self._active_filter)
        if self._zoom_label is not None:
            self._zoom_label.setText(f"{self._zoom_percent}%")
        self._position_controls()

    def _empty_state_text(self) -> str:
        """Returns a filter-aware empty message."""
        if self._active_filter == "all":
            return "No timeline data yet. Generate a chart to populate this view."
        return f"No timeline periods match {self._active_filter.title()} yet."

    def _normalize_events(self, raw_events: Any) -> List[Dict[str, str]]:
        """Normalizes incoming event payloads into a consistent list of typed events."""
        normalized: List[Dict[str, str]] = []

        if isinstance(raw_events, list):
            for raw_event in raw_events:
                if isinstance(raw_event, dict):
                    normalized.append(
                        {
                            "type": self._normalize_event_type(raw_event.get("type")),
                            "confidence": self._normalize_confidence(raw_event.get("confidence")),
                            "summary": str(raw_event.get("summary", "")).strip(),
                        }
                    )
                elif raw_event:
                    normalized.append(
                        {
                            "type": self._normalize_event_type(raw_event),
                            "confidence": "medium",
                            "summary": "",
                        }
                    )
        elif isinstance(raw_events, str) and raw_events.strip():
            normalized.append(
                {
                    "type": self._normalize_event_type(raw_events),
                    "confidence": "medium",
                    "summary": "",
                }
            )

        return normalized

    def _select_primary_event(self, events: List[Dict[str, str]]) -> Dict[str, str]:
        """Chooses the strongest event to drive the main bar style."""
        if not events:
            return {"type": "general", "confidence": "low"}

        return max(
            events,
            key=lambda event: (
                self.CONFIDENCE_ORDER.get(self._normalize_confidence(event.get("confidence")), 0),
                1 if event.get("type") in self.EVENT_COLORS else 0,
            ),
        )

    def _format_event_summary(self, events: List[Dict[str, str]]) -> str:
        """Formats a short in-bar summary such as 'Career | Finance'."""
        if not events:
            return "General"

        seen = []
        for event in events:
            label = self._normalize_event_type(event.get("type")).title()
            if label not in seen:
                seen.append(label)

        return " | ".join(seen)

    def _normalize_event_type(self, value: Any) -> str:
        normalized = str(value or "general").strip().lower()
        if "career" in normalized:
            return "career"
        if "marriage" in normalized or "partnership" in normalized:
            return "marriage"
        if "finance" in normalized or "wealth" in normalized or "income" in normalized:
            return "finance"
        if "health" in normalized or "wellness" in normalized:
            return "health"
        return "general"

    def _normalize_confidence(self, value: Any) -> str:
        normalized = str(value or "medium").strip().lower()
        if normalized in self.CONFIDENCE_ORDER:
            return normalized
        return "medium"

    def _color_for_event(self, event_type: str) -> QColor:
        return QColor(self.EVENT_COLORS.get(event_type, self.EVENT_COLORS["general"]))

    def _style_for_confidence(self, confidence: str) -> Dict[str, int]:
        if confidence == "high":
            return {"fill_alpha": 215, "border_width": 2, "height_delta": 8}
        if confidence == "medium":
            return {"fill_alpha": 180, "border_width": 2, "height_delta": 2}
        return {"fill_alpha": 125, "border_width": 1, "height_delta": -4}

    def _marker_size_for_confidence(self, confidence: str) -> float:
        if confidence == "high":
            return 14.0
        if confidence == "medium":
            return 12.0
        return 10.0

    def _marker_label_for_event(self, event_type: str) -> str:
        event_type = self._normalize_event_type(event_type)
        if event_type == "career":
            return "C"
        if event_type == "marriage":
            return "M"
        if event_type == "finance":
            return "F"
        if event_type == "health":
            return "H"
        return "G"

    def _tooltip_for_event(self, event: Dict[str, str]) -> str:
        event_type = self._normalize_event_type(event.get("type", "general"))
        confidence = self._normalize_confidence(event.get("confidence"))
        summary = str(event.get("summary", "")).strip()

        if event_type == "career":
            message = "Career growth phase"
        elif event_type == "marriage":
            message = "Marriage opportunity"
        elif event_type == "finance":
            message = "Financial opportunity"
        elif event_type == "health":
            message = "Health focus phase"
        else:
            message = "General life phase"

        lines = [message, f"Confidence: {confidence.title()}"]
        if summary:
            lines.append(summary)
        return "\n".join(lines)

    @staticmethod
    def _activation_label_text(code: Any) -> str:
        normalized = str(code or "").strip().lower()
        if normalized == "active_now":
            return "Active Now"
        if normalized == "upcoming":
            return "Upcoming"
        if normalized == "dormant":
            return "Dormant"
        return "Unknown"

    @staticmethod
    def _activation_color(code: Any) -> QColor:
        normalized = str(code or "").strip().lower()
        if normalized == "active_now":
            return QColor("#2563eb")
        if normalized == "upcoming":
            return QColor("#ea580c")
        if normalized == "dormant":
            return QColor("#64748b")
        return QColor("#475569")

    @staticmethod
    def _activation_transition_text(code: Any, trend: Any) -> str:
        normalized_code = str(code or "").strip().lower()
        normalized_trend = str(trend or "").strip().lower()
        if normalized_code == "upcoming" and normalized_trend == "rising":
            return "Upcoming -> Active"
        return ""

    @staticmethod
    def _transit_label(state: Any) -> str:
        normalized = str(state or "").strip().lower()
        if normalized == "amplifying":
            return "Amplifying"
        if normalized == "suppressing":
            return "Suppressing"
        if normalized == "neutral":
            return "Neutral"
        return "Unknown"

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            return 0

    def _period_from_dates(self, start: Any, end: Any) -> str:
        start_date = self._parse_date(start)
        end_date = self._parse_date(end)
        if start_date and end_date:
            return f"{start_date.year}-{end_date.year}"
        if start_date:
            return str(start_date.year)
        return "Upcoming"

    def _detect_timeline_mode(self, data: Dict[str, Any], rows: List[Dict[str, Any]]) -> str:
        if isinstance(data, dict) and str(data.get("mode", "")).strip().lower() == "forecast":
            return "forecast"
        if rows and all(("event" in row and "area" in row) for row in rows[: min(len(rows), 3)]):
            return "forecast"
        return "dasha"

