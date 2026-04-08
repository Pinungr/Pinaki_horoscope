from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Iterable, Mapping


class TimelineService:
    """
    Converts prediction rows into dasha-mapped timeline events.

    Public flow:
    1) extract_dasha_windows(dasha_timeline)
    2) build_timeline_forecast(predictions, dasha_timeline)
    """

    def extract_dasha_windows(self, dasha_timeline: Any) -> list[dict[str, Any]]:
        """
        Normalizes dasha payload into sortable windows.

        Output row shape:
        {
            "mahadasha": "Jupiter",
            "antardasha": "Venus" | None,
            "start": date,
            "end": date,
        }
        """
        timeline_rows = self._extract_timeline_rows(dasha_timeline)
        windows: list[dict[str, Any]] = []

        for row in timeline_rows:
            mahadasha = str(row.get("planet") or row.get("mahadasha") or "").strip()
            maha_start = self._parse_iso_date(row.get("start"))
            maha_end = self._parse_iso_date(row.get("end"))
            if not mahadasha or not maha_start or not maha_end:
                continue

            sub_periods = row.get("sub_periods")
            if isinstance(sub_periods, (list, tuple)):
                sub_windows = self._extract_sub_period_windows(mahadasha, sub_periods)
                if sub_windows:
                    windows.extend(sub_windows)
                    continue

            antardasha = str(row.get("antardasha") or "").strip() or None
            windows.append(
                {
                    "mahadasha": mahadasha,
                    "antardasha": antardasha,
                    "start": maha_start,
                    "end": maha_end,
                }
            )

        return sorted(windows, key=lambda item: (item["start"], item["end"]))

    def build_timeline_forecast(
        self,
        predictions: Iterable[Mapping[str, Any]],
        dasha_timeline: Any,
        *,
        month_granularity: bool = False,
        max_windows_per_prediction: int = 2,
    ) -> dict[str, Any]:
        """
        Maps predictions into event windows using Mahadasha/Antardasha matches.

        Returns:
        {
            "timeline": [
                {
                    "period": "2026-2028",
                    "area": "career",
                    "event": "Career growth and recognition",
                    "confidence": 85,
                    "yoga": "Raj Yoga",
                    "reasoning_link": "..."
                }
            ]
        }
        """
        windows = self.extract_dasha_windows(dasha_timeline)
        timeline: list[dict[str, Any]] = []

        for prediction in predictions or []:
            if not isinstance(prediction, Mapping):
                continue

            matched_windows = self._match_prediction_windows(prediction, windows)
            if not matched_windows:
                continue

            for window in matched_windows[: max(1, int(max_windows_per_prediction))]:
                timeline.append(
                    {
                        "period": self._format_period(window["start"], window["end"], month_granularity),
                        "area": self._normalize_area(str(prediction.get("area", "general"))),
                        "event": self._build_event_label(prediction),
                        "confidence": self._event_confidence(prediction, window),
                        "yoga": str(prediction.get("yoga", "")).strip(),
                        "reasoning_link": self._build_reasoning_link(prediction, window),
                        "start": window["start"].isoformat(),
                        "end": window["end"].isoformat(),
                    }
                )

        timeline.sort(
            key=lambda item: (
                self._parse_iso_date(item.get("start")) or date.max,
                -(self._safe_int(item.get("confidence"))),
            )
        )
        return {"timeline": timeline}

    def _match_prediction_windows(
        self,
        prediction: Mapping[str, Any],
        windows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        timing = prediction.get("timing", {})
        if not isinstance(timing, Mapping):
            timing = {}

        mahadasha = self._normalize_planet_name(timing.get("mahadasha"))
        antardasha = self._normalize_planet_name(timing.get("antardasha"))
        relevance = str(timing.get("relevance", "low")).strip().lower() or "low"

        if not windows:
            return []

        strict_matches = [
            window
            for window in windows
            if (not mahadasha or self._normalize_planet_name(window.get("mahadasha")) == mahadasha)
            and (not antardasha or self._normalize_planet_name(window.get("antardasha")) == antardasha)
        ]
        if strict_matches:
            return strict_matches

        maha_matches = [
            window
            for window in windows
            if mahadasha and self._normalize_planet_name(window.get("mahadasha")) == mahadasha
        ]
        if maha_matches:
            return maha_matches

        if relevance == "low":
            return []
        return []


    def _build_event_label(self, prediction: Mapping[str, Any]) -> str:
        area = self._normalize_area(str(prediction.get("area", "general")))
        strength = str(prediction.get("strength", "medium")).strip().lower() or "medium"
        event_map = {
            ("career", "strong"): "Career growth and recognition",
            ("career", "medium"): "Steady career progress",
            ("career", "weak"): "Slow but meaningful career movement",
            ("finance", "strong"): "Wealth growth and financial gains",
            ("finance", "medium"): "Improving financial stability",
            ("finance", "weak"): "Measured financial progress",
            ("marriage", "strong"): "Strong partnership and marriage support",
            ("marriage", "medium"): "Supportive relationship developments",
            ("marriage", "weak"): "Gradual relationship improvement",
        }
        if (area, strength) in event_map:
            return event_map[(area, strength)]

        text = str(prediction.get("refined_text") or prediction.get("text") or "").strip()
        if text:
            first_sentence = text.split(".")[0].strip()
            if first_sentence:
                return first_sentence[:120]

        return f"Notable {area.replace('_', ' ')} developments"

    def _event_confidence(self, prediction: Mapping[str, Any], window: Mapping[str, Any]) -> int:
        base_score = self._safe_int(prediction.get("score"))
        timing = prediction.get("timing", {})
        if not isinstance(timing, Mapping):
            timing = {}
        relevance = str(timing.get("relevance", "low")).strip().lower() or "low"

        confidence = base_score
        if relevance == "high":
            confidence += 5
        elif relevance == "medium":
            confidence += 2

        antardasha = self._normalize_planet_name(timing.get("antardasha"))
        window_antar = self._normalize_planet_name(window.get("antardasha"))
        if antardasha and window_antar and antardasha == window_antar:
            confidence += 3

        return max(0, min(100, confidence))

    def _build_reasoning_link(self, prediction: Mapping[str, Any], window: Mapping[str, Any]) -> str:
        yoga = str(prediction.get("yoga", "This yoga")).strip() or "This yoga"
        maha = str(window.get("mahadasha", "")).strip()
        antar = str(window.get("antardasha", "")).strip()
        if maha and antar:
            return f"{yoga} aligns with {maha} Mahadasha and {antar} Antardasha, activating this event window."
        if maha:
            return f"{yoga} aligns with {maha} Mahadasha, activating this event window."
        return f"{yoga} supports this event window."

    def _extract_sub_period_windows(
        self,
        mahadasha: str,
        sub_periods: Iterable[Any],
    ) -> list[dict[str, Any]]:
        sub_windows: list[dict[str, Any]] = []
        for sub in sub_periods:
            if not isinstance(sub, Mapping):
                continue
            antardasha = str(sub.get("planet") or sub.get("antardasha") or "").strip()
            sub_start = self._parse_iso_date(sub.get("start"))
            sub_end = self._parse_iso_date(sub.get("end"))
            if not antardasha or not sub_start or not sub_end:
                continue
            sub_windows.append(
                {
                    "mahadasha": mahadasha,
                    "antardasha": antardasha,
                    "start": sub_start,
                    "end": sub_end,
                }
            )
        return sub_windows

    @staticmethod
    def _extract_timeline_rows(dasha_timeline: Any) -> list[dict[str, Any]]:
        if isinstance(dasha_timeline, Mapping):
            rows = dasha_timeline.get("timeline", [])
            if isinstance(rows, list):
                return [dict(row) for row in rows if isinstance(row, Mapping)]
            return []
        if isinstance(dasha_timeline, list):
            return [dict(row) for row in dasha_timeline if isinstance(row, Mapping)]
        return []

    @staticmethod
    def _parse_iso_date(value: Any) -> date | None:
        if not value:
            return None
        try:
            return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _format_period(start: date, end: date, month_granularity: bool) -> str:
        if month_granularity:
            return f"{start.strftime('%b %Y')}\u2013{end.strftime('%b %Y')}"
        return f"{start.year}\u2013{end.year}"


    @staticmethod
    def _normalize_area(area: str) -> str:
        normalized = str(area or "general").strip().lower() or "general"
        if normalized in {"wealth", "financial"}:
            return "finance"
        return normalized

    @staticmethod
    def _normalize_planet_name(planet: Any) -> str:
        return str(planet or "").strip().lower()


