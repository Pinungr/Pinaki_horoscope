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
    _SUPPORTED_LANGUAGES = {"en", "hi", "or"}
    _EVENT_LABELS: Dict[str, Dict[tuple[str, str], str]] = {
        "en": {
            ("career", "strong"): "Career growth and recognition",
            ("career", "medium"): "Steady career progress",
            ("career", "weak"): "Slow but meaningful career movement",
            ("finance", "strong"): "Wealth growth and financial gains",
            ("finance", "medium"): "Improving financial stability",
            ("finance", "weak"): "Measured financial progress",
            ("marriage", "strong"): "Strong partnership and marriage support",
            ("marriage", "medium"): "Supportive relationship developments",
            ("marriage", "weak"): "Gradual relationship improvement",
        },
        "hi": {
            ("career", "strong"): "करियर में वृद्धि और पहचान",
            ("career", "medium"): "करियर में स्थिर प्रगति",
            ("career", "weak"): "धीमी लेकिन अर्थपूर्ण करियर प्रगति",
            ("finance", "strong"): "धन वृद्धि और आर्थिक लाभ",
            ("finance", "medium"): "आर्थिक स्थिरता में सुधार",
            ("finance", "weak"): "संतुलित वित्तीय प्रगति",
            ("marriage", "strong"): "संबंध और विवाह में मजबूत सहयोग",
            ("marriage", "medium"): "रिश्तों में सहायक प्रगति",
            ("marriage", "weak"): "रिश्तों में धीरे-धीरे सुधार",
        },
        "or": {
            ("career", "strong"): "କ୍ୟାରିଅର ଉନ୍ନତି ଏବଂ ପରିଚୟ",
            ("career", "medium"): "ସ୍ଥିର କ୍ୟାରିଅର ପ୍ରଗତି",
            ("career", "weak"): "ଧୀର କିନ୍ତୁ ଅର୍ଥପୂର୍ଣ୍ଣ କ୍ୟାରିଅର ଗତି",
            ("finance", "strong"): "ଧନ ବୃଦ୍ଧି ଏବଂ ଆର୍ଥିକ ଲାଭ",
            ("finance", "medium"): "ଆର୍ଥିକ ସ୍ଥିରତାର ସୁଧାର",
            ("finance", "weak"): "ମାପିତ ଆର୍ଥିକ ପ୍ରଗତି",
            ("marriage", "strong"): "ସମ୍ପର୍କ ଏବଂ ବିବାହରେ ଶକ୍ତିଶାଳୀ ସମର୍ଥନ",
            ("marriage", "medium"): "ସମ୍ପର୍କରେ ସହାୟକ ଉନ୍ନତି",
            ("marriage", "weak"): "ସମ୍ପର୍କରେ ଧୀରେ ଧୀରେ ସୁଧାର",
        },
    }
    _REASONING_LINK_TEMPLATES: Dict[str, Dict[str, str]] = {
        "en": {
            "maha_antar": "{yoga} aligns with {maha} Mahadasha and {antar} Antardasha, activating this event window.",
            "maha": "{yoga} aligns with {maha} Mahadasha, activating this event window.",
            "default": "{yoga} supports this event window.",
            "notable": "Notable {area} developments",
        },
        "hi": {
            "maha_antar": "{yoga} {maha} महादशा और {antar} अंतरदशा के साथ सक्रिय होकर इस समय-खिड़की को मजबूत करता है।",
            "maha": "{yoga} {maha} महादशा के साथ सक्रिय होकर इस समय-खिड़की को मजबूत करता है।",
            "default": "{yoga} इस समय-खिड़की का समर्थन करता है।",
            "notable": "{area} में उल्लेखनीय प्रगति",
        },
        "or": {
            "maha_antar": "{yoga} {maha} ମହାଦଶା ଏବଂ {antar} ଅନ୍ତରଦଶା ସହିତ ମିଳି ଏହି ସମୟ-ଖିଡ଼କିକୁ ସକ୍ରିୟ କରେ।",
            "maha": "{yoga} {maha} ମହାଦଶା ସହିତ ମିଳି ଏହି ସମୟ-ଖିଡ଼କିକୁ ସକ୍ରିୟ କରେ।",
            "default": "{yoga} ଏହି ସମୟ-ଖିଡ଼କିକୁ ସମର୍ଥନ କରେ।",
            "notable": "{area} ରେ ଲକ୍ଷଣୀୟ ଉନ୍ନତି",
        },
    }

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
        language: str = "en",
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
        normalized_language = self._normalize_language(language)
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
                        "event": self._build_event_label(prediction, language=normalized_language),
                        "confidence": self._event_confidence(prediction, window),
                        "yoga": str(prediction.get("yoga", "")).strip(),
                        "reasoning_link": self._build_reasoning_link(
                            prediction,
                            window,
                            language=normalized_language,
                        ),
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


    def _build_event_label(self, prediction: Mapping[str, Any], *, language: str) -> str:
        area = self._normalize_area(str(prediction.get("area", "general")))
        strength = str(prediction.get("strength", "medium")).strip().lower() or "medium"
        event_map = self._EVENT_LABELS.get(language, self._EVENT_LABELS["en"])
        if (area, strength) in event_map:
            return event_map[(area, strength)]

        text = str(prediction.get("refined_text") or prediction.get("text") or "").strip()
        if text:
            first_sentence = text.split(".")[0].strip()
            if first_sentence:
                return first_sentence[:120]

        templates = self._REASONING_LINK_TEMPLATES.get(language, self._REASONING_LINK_TEMPLATES["en"])
        return templates["notable"].format(area=area.replace("_", " "))

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

    def _build_reasoning_link(
        self,
        prediction: Mapping[str, Any],
        window: Mapping[str, Any],
        *,
        language: str,
    ) -> str:
        yoga = str(prediction.get("yoga", "This yoga")).strip() or "This yoga"
        maha = str(window.get("mahadasha", "")).strip()
        antar = str(window.get("antardasha", "")).strip()
        templates = self._REASONING_LINK_TEMPLATES.get(language, self._REASONING_LINK_TEMPLATES["en"])
        if maha and antar:
            return templates["maha_antar"].format(yoga=yoga, maha=maha, antar=antar)
        if maha:
            return templates["maha"].format(yoga=yoga, maha=maha)
        return templates["default"].format(yoga=yoga)

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

    def _normalize_language(self, language: str) -> str:
        normalized = str(language or "en").strip().lower() or "en"
        if normalized not in self._SUPPORTED_LANGUAGES:
            return "en"
        return normalized


