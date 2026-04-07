from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List

from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsScene, QGraphicsSimpleTextItem, QGraphicsView


class TimelineBarItem(QGraphicsRectItem):
    """Clickable graphics item that delegates dasha selection back to the widget."""

    def __init__(self, rect: QRectF, payload: Dict[str, Any], click_handler, parent=None):
        super().__init__(rect, parent)
        self._payload = payload
        self._click_handler = click_handler
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if callable(self._click_handler):
            self._click_handler(self._payload)
        super().mousePressEvent(event)


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
    ROW_HEIGHT = 72
    BAR_HEIGHT = 24
    MIN_BAR_WIDTH = 120
    PIXELS_PER_DAY = 0.18
    EVENT_COLORS = {
        "career": QColor("#3b82f6"),
        "marriage": QColor("#ec4899"),
        "finance": QColor("#22c55e"),
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
        self._timeline_rows: List[Dict[str, Any]] = []

        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setMinimumHeight(280)
        self.setStyleSheet("background: #fbfbfd; border: 1px solid #d9dce3;")

        self.set_timeline_data({"timeline": []})

    def set_timeline_data(self, data: Dict[str, Any]) -> None:
        """Loads timeline JSON data and redraws the scene."""
        timeline = data.get("timeline", []) if isinstance(data, dict) else []
        self._timeline_rows = [row for row in timeline if isinstance(row, dict)]
        self._redraw_scene()

    def clear_timeline(self) -> None:
        """Clears all rendered timeline content."""
        self.set_timeline_data({"timeline": []})

    def _redraw_scene(self) -> None:
        self._scene.clear()

        if not self._timeline_rows:
            empty_text = self._scene.addText("No timeline data available.")
            empty_text.setDefaultTextColor(QColor("#6b7280"))
            empty_text.setPos(self.LEFT_MARGIN, self.TOP_MARGIN)
            self._scene.setSceneRect(QRectF(0, 0, 640, 180))
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
            invalid_text.setPos(self.LEFT_MARGIN, self.TOP_MARGIN)
            self._scene.setSceneRect(QRectF(0, 0, 680, 180))
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
        title_item.setPos(self.LEFT_MARGIN, 0)

        self._draw_legend(title_item.boundingRect().width() + self.LEFT_MARGIN + 24, 2)

        for index, row in enumerate(parsed_rows):
            self._draw_timeline_row(
                row=row,
                row_index=index,
                timeline_start=timeline_start,
                timeline_width=timeline_width,
                total_days=total_days,
            )

        scene_height = self.TOP_MARGIN + (len(parsed_rows) * self.ROW_HEIGHT) + self.BOTTOM_MARGIN
        scene_width = self.LEFT_MARGIN + timeline_width + self.RIGHT_MARGIN
        self._scene.setSceneRect(QRectF(0, 0, scene_width, scene_height))

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

        row_top = self.TOP_MARGIN + 22 + (row_index * self.ROW_HEIGHT)
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

    def _draw_legend(self, x: float, y: float) -> None:
        """Draws a small color legend for event types and confidence emphasis."""
        legend_entries = [
            ("Career", self.EVENT_COLORS["career"]),
            ("Marriage", self.EVENT_COLORS["marriage"]),
            ("Finance", self.EVENT_COLORS["finance"]),
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

    def _handle_period_click(self, payload: Dict[str, Any]) -> None:
        """Emits the selected dasha payload for controller-level handling."""
        self.period_selected.emit(payload)

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
                        }
                    )
                elif raw_event:
                    normalized.append(
                        {
                            "type": self._normalize_event_type(raw_event),
                            "confidence": "medium",
                        }
                    )
        elif isinstance(raw_events, str) and raw_events.strip():
            normalized.append(
                {
                    "type": self._normalize_event_type(raw_events),
                    "confidence": "medium",
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
        else:
            message = "General life phase"

        lines = [message, f"Confidence: {confidence.title()}"]
        if summary:
            lines.append(summary)
        return "\n".join(lines)
