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
    _ACTIVATION_LABELS = {"active_now", "upcoming", "dormant"}

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
        today = date.today()

        for prediction in predictions or []:
            if not isinstance(prediction, Mapping):
                continue

            matched_windows = self._match_prediction_windows(prediction, windows)
            if not matched_windows:
                continue

            trend_context = self._compute_activation_trend_context(prediction, windows, today=today)
            for window in matched_windows[: max(1, int(max_windows_per_prediction))]:
                timing = prediction.get("timing", {})
                if not isinstance(timing, Mapping):
                    timing = {}
                activation_level = str(
                    prediction.get("activation_level", timing.get("activation_level", timing.get("relevance", "low")))
                ).strip().lower() or "low"
                dasha_evidence = self._normalize_evidence(
                    prediction.get("dasha_evidence", timing.get("dasha_evidence", []))
                )
                if not dasha_evidence:
                    maha = str(window.get("mahadasha", "")).strip()
                    antar = str(window.get("antardasha", "")).strip()
                    if maha and antar:
                        dasha_evidence = [
                            f"Active dasha window: {maha} Mahadasha with {antar} Antardasha."
                        ]
                    elif maha:
                        dasha_evidence = [f"Active dasha window: {maha} Mahadasha."]
                    else:
                        dasha_evidence = ["Timing is mapped from the current dasha window."]
                activation_score = self._safe_int(
                    prediction.get("activation_score", timing.get("activation_score"))
                )
                projected_score = self._project_activation_for_window(
                    prediction,
                    window,
                    base_score=activation_score,
                    today=today,
                )
                activation_label = self._resolve_activation_label(
                    window=window,
                    prediction=prediction,
                    projected_score=projected_score,
                    today=today,
                    trend_context=trend_context,
                )
                source_factors = self._build_source_factors(
                    prediction=prediction,
                    window=window,
                    activation_label=activation_label,
                    projected_score=projected_score,
                    trend_context=trend_context,
                    dasha_evidence=dasha_evidence,
                    today=today,
                )
                prediction_text = str(
                    prediction.get("final_narrative")
                    or prediction.get("refined_text")
                    or prediction.get("text")
                    or self._build_event_label(prediction, language=normalized_language)
                ).strip()
                timeline.append(
                    {
                        "period": self._format_period(window["start"], window["end"], month_granularity),
                        "area": self._normalize_area(str(prediction.get("area", "general"))),
                        "event": self._build_event_label(prediction, language=normalized_language),
                        "prediction": prediction_text,
                        "confidence": self._event_confidence(prediction, window),
                        "yoga": str(prediction.get("yoga", "")).strip(),
                        "activation_level": activation_level,
                        "activation_score": projected_score,
                        "activation_label": activation_label,
                        "activation_trend": trend_context.get("trend", "stable"),
                        "strength_level": str(prediction.get("strength", "")).strip().lower() or "unknown",
                        "strength_score": self._safe_int(prediction.get("strength_score")),
                        "agreement_level": str(prediction.get("agreement_level", "medium")).strip().lower() or "medium",
                        "concordance_score": prediction.get("concordance_score", None),
                        "transit_support_state": str(
                            (
                                prediction.get("transit", {})
                                if isinstance(prediction.get("transit"), Mapping)
                                else {}
                            ).get("support_state", "neutral")
                        ).strip().lower()
                        or "neutral",
                        "dasha_evidence": dasha_evidence,
                        "source_factors": source_factors,
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

    def _compute_activation_trend_context(
        self,
        prediction: Mapping[str, Any],
        windows: list[dict[str, Any]],
        *,
        today: date,
    ) -> dict[str, Any]:
        if not windows:
            return {"trend": "stable", "current_score": 0, "next_score": 0}

        timing = prediction.get("timing", {})
        if not isinstance(timing, Mapping):
            timing = {}
        base_score = self._safe_int(prediction.get("activation_score", timing.get("activation_score")))
        if base_score <= 0:
            base_score = self._safe_int(prediction.get("score"))

        current_window = self._find_current_window(windows, today=today)
        next_window = self._find_next_window(windows, today=today)

        current_score = (
            self._project_activation_for_window(prediction, current_window, base_score=base_score, today=today)
            if current_window
            else 0
        )
        next_score = (
            self._project_activation_for_window(prediction, next_window, base_score=base_score, today=today)
            if next_window
            else 0
        )
        delta = next_score - current_score
        if delta >= 8:
            trend = "rising"
        elif delta <= -8:
            trend = "falling"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "current_score": current_score,
            "next_score": next_score,
            "current_window": current_window,
            "next_window": next_window,
        }

    def _project_activation_for_window(
        self,
        prediction: Mapping[str, Any],
        window: Mapping[str, Any] | None,
        *,
        base_score: int,
        today: date,
    ) -> int:
        if not isinstance(window, Mapping):
            return max(0, min(100, base_score))

        support = self._window_support_type(prediction, window)
        adjustment = 0
        if support == "maha_antar":
            adjustment += 12
        elif support == "maha":
            adjustment += 7
        elif support == "antar":
            adjustment += 4
        else:
            adjustment -= 18

        start = window.get("start")
        if isinstance(start, date) and start > today:
            days_to_start = (start - today).days
            if days_to_start <= 540 and support in {"maha_antar", "maha", "antar"}:
                adjustment += 4
            elif days_to_start > 540:
                adjustment -= 3

        return max(0, min(100, int(round(base_score + adjustment))))

    def _resolve_activation_label(
        self,
        *,
        window: Mapping[str, Any],
        prediction: Mapping[str, Any],
        projected_score: int,
        today: date,
        trend_context: Mapping[str, Any],
    ) -> str:
        support = self._window_support_type(prediction, window)
        start = window.get("start")
        end = window.get("end")
        is_current = isinstance(start, date) and isinstance(end, date) and start <= today <= end
        is_future = isinstance(start, date) and start > today

        if is_current and support in {"maha_antar", "maha", "antar"} and projected_score >= 67:
            return "active_now"

        trend = str(trend_context.get("trend", "stable")).strip().lower() or "stable"
        if is_future and support in {"maha_antar", "maha", "antar"}:
            if projected_score >= 40 or trend == "rising":
                return "upcoming"

        return "dormant"

    def _build_source_factors(
        self,
        *,
        prediction: Mapping[str, Any],
        window: Mapping[str, Any],
        activation_label: str,
        projected_score: int,
        trend_context: Mapping[str, Any],
        dasha_evidence: list[str],
        today: date,
    ) -> list[str]:
        factors: list[str] = []

        for line in dasha_evidence:
            text = str(line or "").strip()
            if text and text not in factors:
                factors.append(text)

        support = self._window_support_type(prediction, window)
        maha = str(window.get("mahadasha", "")).strip()
        antar = str(window.get("antardasha", "")).strip()
        if support == "maha_antar" and maha and antar:
            factors.append(f"{maha} Mahadasha and {antar} Antardasha both support this promise.")
        elif support == "maha" and maha:
            factors.append(f"{maha} Mahadasha is the main activation driver.")
        elif support == "antar" and antar:
            factors.append(f"{antar} Antardasha provides focused activation support.")
        else:
            factors.append("Current window has limited direct dasha support for this promise.")

        trend = str(trend_context.get("trend", "stable")).strip().lower() or "stable"
        next_window = trend_context.get("next_window")
        if trend == "rising" and isinstance(next_window, Mapping):
            next_maha = str(next_window.get("mahadasha", "")).strip()
            next_antar = str(next_window.get("antardasha", "")).strip()
            start = next_window.get("start")
            if next_maha and next_antar and isinstance(start, date):
                if start > today:
                    factors.append(f"{next_antar} Antardasha under {next_maha} Mahadasha is starting soon.")
        elif trend == "falling":
            factors.append("Activation is expected to soften in the next dasha window.")

        factors.append(f"Projected activation score for this window: {projected_score}.")
        if activation_label == "active_now":
            factors.append("This window is currently active with high dasha support.")
        elif activation_label == "upcoming":
            factors.append("Support is strengthening in a future dasha window.")
        else:
            factors.append("This window remains comparatively dormant.")

        return factors[:8]

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
        relevance = str(timing.get("activation_level", timing.get("relevance", "low"))).strip().lower() or "low"

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

    def _window_support_type(
        self,
        prediction: Mapping[str, Any],
        window: Mapping[str, Any],
    ) -> str:
        timing = prediction.get("timing", {})
        if not isinstance(timing, Mapping):
            timing = {}

        mahadasha = self._normalize_planet_name(timing.get("mahadasha"))
        antardasha = self._normalize_planet_name(timing.get("antardasha"))
        window_maha = self._normalize_planet_name(window.get("mahadasha"))
        window_antar = self._normalize_planet_name(window.get("antardasha"))

        maha_match = bool(mahadasha and window_maha and mahadasha == window_maha)
        antar_match = bool(antardasha and window_antar and antardasha == window_antar)
        if maha_match and antar_match:
            return "maha_antar"
        if maha_match:
            return "maha"
        if antar_match:
            return "antar"
        return "none"


    def _build_event_label(self, prediction: Mapping[str, Any], *, language: str) -> str:
        area = self._normalize_area(str(prediction.get("area", "general")))
        strength = str(prediction.get("strength", "medium")).strip().lower() or "medium"
        event_map = self._EVENT_LABELS.get(language, self._EVENT_LABELS["en"])
        if (area, strength) in event_map:
            return event_map[(area, strength)]

        text = str(
            prediction.get("final_narrative")
            or prediction.get("refined_text")
            or prediction.get("text")
            or ""
        ).strip()
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
        relevance = str(timing.get("activation_level", timing.get("relevance", "low"))).strip().lower() or "low"
        activation_score = self._safe_int(timing.get("activation_score"))

        confidence = base_score
        if relevance == "high":
            confidence += 5
        elif relevance == "medium":
            confidence += 2
        if activation_score > 0:
            confidence += max(-3, min(6, int(round((activation_score - 50) / 12))))

        antardasha = self._normalize_planet_name(timing.get("antardasha"))
        window_antar = self._normalize_planet_name(window.get("antardasha"))
        if antardasha and window_antar and antardasha == window_antar:
            confidence += 3

        return max(0, min(100, confidence))

    @staticmethod
    def _normalize_evidence(raw_evidence: Any) -> list[str]:
        if not isinstance(raw_evidence, (list, tuple, set)):
            return []
        evidence: list[str] = []
        for row in raw_evidence:
            text = str(row or "").strip()
            if text and text not in evidence:
                evidence.append(text)
        return evidence[:8]

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
    def _find_current_window(windows: list[dict[str, Any]], *, today: date) -> dict[str, Any] | None:
        for window in windows:
            start = window.get("start")
            end = window.get("end")
            if isinstance(start, date) and isinstance(end, date) and start <= today <= end:
                return window
        return None

    @staticmethod
    def _find_next_window(windows: list[dict[str, Any]], *, today: date) -> dict[str, Any] | None:
        future = [
            window
            for window in windows
            if isinstance(window.get("start"), date) and window.get("start") > today
        ]
        if not future:
            return None
        return sorted(future, key=lambda item: item.get("start"))[0]

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


