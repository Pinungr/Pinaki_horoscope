from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Dict, Iterable, Mapping

from app.services.intent_keywords import (
    INTENT_KEYWORDS,
    detect_intent as _shared_detect_intent,
    normalize_area as _shared_normalize_area,
)


class EventService:
    """
    Event prediction engine for query-driven timeline answers.

    Input:
    - user query
    - predictions (optional for future scoring extensions)
    - timeline data (from timeline_service.build_timeline_forecast)
    - reasoning data
    """

    AREA_ALIASES: Dict[str, str] = {
        "wealth": "finance",
        "financial": "finance",
    }
    _SUPPORTED_LANGUAGES = {"en", "hi", "or"}
    _TEMPLATES: Dict[str, Dict[str, str]] = {
        "en": {
            "no_window": "I do not see a clear {intent} event window yet in the current dasha timeline.",
            "phrase_career": "career growth",
            "phrase_marriage": "marriage progress",
            "phrase_finance": "financial improvement",
            "phrase_health": "health improvement",
            "phrase_default": "notable results",
            "answer_period_label": "You are likely to experience {phrase} between {period}. {label}.",
            "answer_period_only": "You are likely to experience {phrase} between {period}.",
            "answer_label_only": "You are likely to experience {phrase}. {label}.",
            "answer_default": "You are likely to experience {phrase} soon.",
        },
        "hi": {
            "no_window": "वर्तमान दशा-समयरेखा में अभी {intent} के लिए स्पष्ट घटना-समय नहीं दिख रहा है।",
            "phrase_career": "करियर में प्रगति",
            "phrase_marriage": "विवाह/रिश्ते में प्रगति",
            "phrase_finance": "आर्थिक सुधार",
            "phrase_health": "स्वास्थ्य में सुधार",
            "phrase_default": "उल्लेखनीय परिणाम",
            "answer_period_label": "आपको {period} के दौरान {phrase} का अनुभव होने की संभावना है। {label}।",
            "answer_period_only": "आपको {period} के दौरान {phrase} का अनुभव होने की संभावना है।",
            "answer_label_only": "आपको {phrase} का अनुभव होने की संभावना है। {label}।",
            "answer_default": "आपको जल्द ही {phrase} का अनुभव होने की संभावना है।",
        },
        "or": {
            "no_window": "ବର୍ତ୍ତମାନ ଦଶା ସମୟରେଖାରେ {intent} ପାଇଁ ଏପର୍ଯ୍ୟନ୍ତ ସ୍ପଷ୍ଟ ଘଟଣା-ସମୟ ଦେଖାଯାଉନି।",
            "phrase_career": "କ୍ୟାରିଅର ଉନ୍ନତି",
            "phrase_marriage": "ବିବାହ/ସମ୍ପର୍କ ଉନ୍ନତି",
            "phrase_finance": "ଆର୍ଥିକ ସୁଧାର",
            "phrase_health": "ସ୍ୱାସ୍ଥ୍ୟ ସୁଧାର",
            "phrase_default": "ଲକ୍ଷଣୀୟ ଫଳ",
            "answer_period_label": "{period} ସମୟରେ ଆପଣ {phrase} ଅନୁଭବ କରିବାର ସମ୍ଭାବନା ଅଛି। {label}।",
            "answer_period_only": "{period} ସମୟରେ ଆପଣ {phrase} ଅନୁଭବ କରିବାର ସମ୍ଭାବନା ଅଛି।",
            "answer_label_only": "ଆପଣ {phrase} ଅନୁଭବ କରିବାର ସମ୍ଭାବନା ଅଛି। {label}।",
            "answer_default": "ଶୀଘ୍ର ଆପଣ {phrase} ଅନୁଭବ କରିପାରନ୍ତି।",
        },
    }

    def detect_intent(self, user_query: str) -> str:
        """Delegates to the shared intent detector for consistency with the chat pipeline."""
        return _shared_detect_intent(user_query)

    def is_specific_query(self, user_query: str) -> bool:
        return self.detect_intent(user_query) != "general"

    def predict_event(
        self,
        *,
        user_query: str,
        predictions: Iterable[Mapping[str, Any]] | None,
        timeline_data: Any,
        reasoning_data: Iterable[Mapping[str, Any]] | None,
        language: str = "en",
    ) -> dict[str, Any]:
        normalized_language = self._normalize_language(language)
        templates = self._TEMPLATES[normalized_language]
        intent = self.detect_intent(user_query)
        if intent == "general":
            return {
                "answer": "",
                "confidence": 0,
                "supporting_events": [],
                "reasoning": [],
            }

        timeline_rows = self._extract_timeline_rows(timeline_data)
        matched = self.filter_events_by_area(timeline_rows, intent)
        top_events = self.pick_top_events(matched, max_events=3)
        reasoning_rows = self._filter_reasoning_by_area(reasoning_data, intent)

        if not top_events:
            return {
                "answer": templates["no_window"].format(intent=intent),
                "confidence": 0,
                "supporting_events": [],
                "reasoning": reasoning_rows,
            }

        top_event = top_events[0]
        answer = self._build_answer(intent, top_event, language=normalized_language)
        confidence = self._safe_int(top_event.get("confidence"))

        return {
            "answer": answer,
            "confidence": confidence,
            "supporting_events": top_events,
            "reasoning": reasoning_rows,
            "intent": intent,
        }

    def filter_events_by_area(
        self,
        timeline_rows: Iterable[Mapping[str, Any]],
        intent: str,
    ) -> list[dict[str, Any]]:
        target = self._normalize_area(intent)
        matched: list[dict[str, Any]] = []
        for row in timeline_rows or []:
            if not isinstance(row, Mapping):
                continue
            area = self._normalize_area(str(row.get("area", "")).strip().lower())
            if area != target:
                continue
            matched.append(dict(row))
        return matched

    def pick_top_events(
        self,
        events: Iterable[Mapping[str, Any]],
        *,
        max_events: int = 3,
    ) -> list[dict[str, Any]]:
        today = date.today()

        def sort_key(event: Mapping[str, Any]) -> tuple[int, int, int]:
            confidence = self._safe_int(event.get("confidence"))
            start = self._parse_iso_date(event.get("start"))
            if start is None:
                return (-confidence, 2, 10**9)

            delta_days = (start - today).days
            future_bucket = 0 if delta_days >= 0 else 1
            return (-confidence, future_bucket, abs(delta_days))

        ranked = [dict(event) for event in events or [] if isinstance(event, Mapping)]
        ranked.sort(key=sort_key)
        return ranked[: max(1, int(max_events))]

    def _build_answer(self, intent: str, event: Mapping[str, Any], *, language: str) -> str:
        templates = self._TEMPLATES.get(language, self._TEMPLATES["en"])
        period = str(event.get("period", "")).strip()
        label = str(event.get("event", "")).strip()

        phrase_map = {
            "career": templates["phrase_career"],
            "marriage": templates["phrase_marriage"],
            "finance": templates["phrase_finance"],
            "health": templates["phrase_health"],
        }
        phrase = phrase_map.get(intent, templates["phrase_default"])

        if period and label:
            return templates["answer_period_label"].format(phrase=phrase, period=period, label=label)
        if period:
            return templates["answer_period_only"].format(phrase=phrase, period=period)
        if label:
            return templates["answer_label_only"].format(phrase=phrase, label=label)
        return templates["answer_default"].format(phrase=phrase)

    def _filter_reasoning_by_area(
        self,
        reasoning_data: Iterable[Mapping[str, Any]] | None,
        intent: str,
    ) -> list[dict[str, Any]]:
        target = self._normalize_area(intent)
        rows: list[dict[str, Any]] = []
        for row in reasoning_data or []:
            if not isinstance(row, Mapping):
                continue
            area = self._normalize_area(str(row.get("area", "")).strip().lower())
            if area == target:
                rows.append(dict(row))
        return rows

    def _extract_timeline_rows(self, timeline_data: Any) -> list[dict[str, Any]]:
        if isinstance(timeline_data, Mapping):
            rows = timeline_data.get("timeline", [])
            if isinstance(rows, list):
                return [dict(row) for row in rows if isinstance(row, Mapping)]
            return []
        if isinstance(timeline_data, list):
            return [dict(row) for row in timeline_data if isinstance(row, Mapping)]
        return []

    def _normalize_area(self, area: str) -> str:
        normalized = str(area or "").strip().lower() or "general"
        return self.AREA_ALIASES.get(normalized, normalized)

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

    def _normalize_language(self, language: str) -> str:
        normalized = str(language or "en").strip().lower() or "en"
        if normalized not in self._SUPPORTED_LANGUAGES:
            return "en"
        return normalized
