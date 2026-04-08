from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict
from core.utils.chart_utils import get_planet_house, normalize_planet_name

from app.utils.runtime_paths import resolve_resource


class PredictionService:
    """Loads localized prediction meanings from a key-based JSON registry."""

    DEFAULT_LANGUAGE = "en"
    HOUSE_AREA_MAP: Dict[int, str] = {
        1: "self",
        2: "wealth",
        3: "communication",
        4: "home",
        5: "education",
        6: "health",
        7: "marriage",
        8: "transformation",
        9: "luck",
        10: "career",
        11: "gains",
        12: "loss/spiritual",
    }
    KNOWN_PLANETS = {
        "sun",
        "moon",
        "mars",
        "mercury",
        "jupiter",
        "venus",
        "saturn",
        "rahu",
        "ketu",
    }

    def __init__(self, meanings_path: Path | None = None) -> None:
        self.meanings_path = meanings_path or resolve_resource("core", "predictions", "meanings.json")
        self._meanings: Dict[str, Dict[str, Any]] | None = None

    def get_prediction(self, rule_key: Any, language: str | None = None) -> str:
        normalized_key = str(rule_key or "").strip()
        if not normalized_key:
            return ""

        normalized_language = str(language or self.DEFAULT_LANGUAGE).strip().lower() or self.DEFAULT_LANGUAGE
        meanings = self._load_meanings()
        meaning_entry = meanings.get(normalized_key, {})
        if not isinstance(meaning_entry, dict):
            return ""

        localized_text = meaning_entry.get(normalized_language)
        if localized_text:
            return str(localized_text).strip()

        fallback_text = meaning_entry.get(self.DEFAULT_LANGUAGE)
        if fallback_text:
            return str(fallback_text).strip()

        return ""

    def get_weight(self, rule_key: Any) -> float:
        normalized_key = str(rule_key or "").strip()
        if not normalized_key:
            return 0.0

        meaning_entry = self._load_meanings().get(normalized_key, {})
        if not isinstance(meaning_entry, dict):
            return 0.0

        raw_weight = meaning_entry.get("weight", 0.0)
        try:
            return float(raw_weight or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def map_yoga_to_planets(self, yoga: Any) -> list[str]:
        """
        Extracts involved planets for one yoga definition/result in normalized form.

        Returns lowercase planet ids (e.g. ["moon", "jupiter"]).
        """
        extracted: list[str] = []
        seen: set[str] = set()

        def _add(raw_planet: Any) -> None:
            normalized = normalize_planet_name(raw_planet)
            if normalized and normalized in self.KNOWN_PLANETS and normalized not in seen:
                seen.add(normalized)
                extracted.append(normalized)

        for key in ("key_planets", "planets"):
            raw_values = self._read_value(yoga, key, [])
            if isinstance(raw_values, (list, tuple, set)):
                for item in raw_values:
                    _add(item)

        for key in ("planet", "from", "to", "from_planet", "to_planet"):
            _add(self._read_value(yoga, key))

        if not extracted:
            yoga_id = str(self._read_value(yoga, "id", self._read_value(yoga, "yoga", "")) or "").lower()
            for planet in self.KNOWN_PLANETS:
                if planet in yoga_id and planet not in seen:
                    seen.add(planet)
                    extracted.append(planet)

        return extracted

    def evaluate_dasha_relevance(
        self,
        yoga: Any,
        dasha_data: Any,
        *,
        reference_date: date | None = None,
    ) -> Dict[str, Any]:
        """
        Computes dasha relevance for one yoga.

        Output shape:
        {
            "mahadasha": "Jupiter",
            "antardasha": "Venus",
            "relevance": "high" | "medium" | "low",
            "matched_planets": [...],
            "score_multiplier": float
        }
        """
        yoga_planets = self.map_yoga_to_planets(yoga)
        dasha_context = self.get_current_dasha_context(dasha_data, reference_date=reference_date)

        mahadasha_lord = normalize_planet_name(dasha_context.get("mahadasha"))
        antardasha_lord = normalize_planet_name(dasha_context.get("antardasha"))
        matched_planets: list[str] = []

        maha_match = mahadasha_lord in yoga_planets if mahadasha_lord else False
        antar_match = antardasha_lord in yoga_planets if antardasha_lord else False
        if maha_match and mahadasha_lord:
            matched_planets.append(mahadasha_lord)
        if antar_match and antardasha_lord and antardasha_lord not in matched_planets:
            matched_planets.append(antardasha_lord)

        if maha_match and antar_match:
            relevance = "high"
            multiplier = 1.25
        elif maha_match:
            relevance = "high"
            multiplier = 1.15
        elif antar_match:
            relevance = "medium"
            multiplier = 1.08
        else:
            relevance = "low"
            multiplier = 1.0

        return {
            "mahadasha": dasha_context.get("mahadasha"),
            "antardasha": dasha_context.get("antardasha"),
            "relevance": relevance,
            "matched_planets": matched_planets,
            "score_multiplier": multiplier,
        }

    def build_timing_text(self, timing: Any) -> str:
        if not isinstance(timing, dict):
            return ""

        mahadasha = str(timing.get("mahadasha") or "").strip()
        antardasha = str(timing.get("antardasha") or "").strip()
        relevance = str(timing.get("relevance") or "low").strip().lower() or "low"

        if not mahadasha and not antardasha:
            return ""

        if relevance == "high":
            if mahadasha and antardasha:
                return (
                    f"This effect is strongest during {mahadasha} Mahadasha, "
                    f"especially in {antardasha} Antardasha."
                )
            if mahadasha:
                return f"This effect is stronger during {mahadasha} Mahadasha."
            return f"This effect is especially active during {antardasha} Antardasha."

        if relevance == "medium":
            if antardasha:
                return f"This effect may rise during {antardasha} Antardasha."
            if mahadasha:
                return f"This effect may rise during {mahadasha} Mahadasha."
            return ""

        if mahadasha:
            return f"Timing support is presently limited, with a milder influence in {mahadasha} Mahadasha."
        return f"Timing support is presently limited, with a milder influence in {antardasha} Antardasha."

    def get_current_dasha_context(
        self,
        dasha_data: Any,
        *,
        reference_date: date | None = None,
    ) -> Dict[str, Any]:
        """
        Resolves current Mahadasha and Antardasha from available dasha payload.
        """
        today = reference_date or date.today()
        timeline = self._extract_timeline_rows(dasha_data)
        current = self._find_current_dasha_period(timeline, today)
        if not current:
            return {"mahadasha": None, "antardasha": None}

        antardasha = current.get("antardasha")
        if not antardasha:
            sub_periods = current.get("sub_periods")
            if isinstance(sub_periods, (list, tuple)):
                active_sub = self._find_current_dasha_period(sub_periods, today)
                if active_sub:
                    antardasha = active_sub.get("planet")

        return {
            "mahadasha": current.get("planet"),
            "antardasha": antardasha,
        }

    def get_house_area(self, house: Any) -> str:
        try:
            house_num = int(house)
        except (TypeError, ValueError):
            return "general"
        return self.HOUSE_AREA_MAP.get(house_num, "general")

    def extract_prediction_context(self, yoga: Any, chart_data: Any) -> Dict[str, Any]:
        yoga_name = str(self._read_value(yoga, "id", self._read_value(yoga, "yoga", "")) or "").strip()
        strength = str(
            self._read_value(yoga, "strength_level", self._read_value(yoga, "strength", "medium")) or "medium"
        ).strip().lower()
        if strength not in {"strong", "medium", "weak"}:
            strength = "medium"

        house = self._coerce_house(
            self._read_value(
                yoga,
                "house",
                self._read_value(yoga, "to_house", self._read_value(yoga, "from_house")),
            )
        )
        key_planets = self._normalize_planet_list(self._read_value(yoga, "key_planets", []))
        if house is None:
            for planet in key_planets:
                house = self._resolve_planet_house(chart_data, planet)
                if house is not None:
                    break

        return {
            "yoga": yoga_name,
            "house": house,
            "area": self.get_house_area(house),
            "strength": strength,
        }

    def generate_contextual_prediction(
        self,
        yoga: Any,
        chart_data: Any,
        language: str | None = None,
    ) -> Dict[str, str]:
        context = self.extract_prediction_context(yoga, chart_data)
        strength = {
            "level": context.get("strength", "medium"),
            "score": self._read_value(yoga, "strength_score", None),
        }
        return self.generate_contextual(
            chart=chart_data,
            yoga=yoga,
            strength=strength,
            language=language,
        )

    def generate_contextual(
        self,
        chart: Any,
        yoga: Any,
        strength: Any,
        language: str | None = None,
    ) -> Dict[str, str]:
        context = self.extract_prediction_context(yoga, chart)
        yoga_name = str(context.get("yoga", "")).strip()
        area = str(context.get("area", "general")).strip() or "general"
        strength_level = self._normalize_strength_level(strength, fallback=context.get("strength", "medium"))

        area_text = self._build_area_text(area)
        strength_text = self._build_strength_text(strength_level)
        base_text = self.get_prediction(yoga_name, language)
        combined = " ".join(part for part in [area_text, strength_text, base_text] if part).strip()

        return {
            "area": area,
            "text": combined,
            "yoga": yoga_name,
            "strength": strength_level,
        }

    def _load_meanings(self) -> Dict[str, Dict[str, Any]]:
        if self._meanings is not None:
            return self._meanings

        try:
            payload = json.loads(self.meanings_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}

        if not isinstance(payload, dict):
            payload = {}

        self._meanings = {
            str(key).strip(): value
            for key, value in payload.items()
            if isinstance(value, dict)
        }
        return self._meanings

    @staticmethod
    def _read_value(payload: Any, key: str, default: Any = None) -> Any:
        if isinstance(payload, dict):
            return payload.get(key, default)
        return getattr(payload, key, default)

    @staticmethod
    def _coerce_house(raw_house: Any) -> int | None:
        try:
            house = int(raw_house)
        except (TypeError, ValueError):
            return None
        if 1 <= house <= 12:
            return house
        return None

    @staticmethod
    def _normalize_planet_list(planets: Any) -> list[str]:
        if not isinstance(planets, (list, tuple, set)):
            return []
        normalized: list[str] = []
        for planet in planets:
            planet_id = normalize_planet_name(planet)
            if planet_id and planet_id not in normalized:
                normalized.append(planet_id)
        return normalized

    def _resolve_planet_house(self, chart_data: Any, planet_name: str) -> int | None:
        placements = getattr(chart_data, "placements", None)
        if isinstance(placements, dict):
            placement = placements.get(normalize_planet_name(planet_name))
            if placement is not None:
                return self._coerce_house(getattr(placement, "house", None))

        return get_planet_house(chart_data, planet_name)

    @staticmethod
    def _normalize_strength_level(strength: Any, *, fallback: Any = "medium") -> str:
        if isinstance(strength, dict):
            candidate = strength.get("level", fallback)
        else:
            candidate = strength if strength is not None else fallback

        normalized = str(candidate or "medium").strip().lower() or "medium"
        if normalized not in {"strong", "medium", "weak"}:
            return "medium"
        return normalized

    @staticmethod
    def _extract_timeline_rows(dasha_data: Any) -> list[Dict[str, Any]]:
        if isinstance(dasha_data, dict):
            rows = dasha_data.get("timeline", [])
            return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
        if isinstance(dasha_data, list):
            return [row for row in dasha_data if isinstance(row, dict)]
        return []

    @staticmethod
    def _parse_iso_date(raw_date: Any) -> date | None:
        if not raw_date:
            return None
        try:
            return datetime.strptime(str(raw_date).strip(), "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return None

    def _find_current_dasha_period(self, periods: Any, target_date: date) -> Dict[str, Any] | None:
        if not isinstance(periods, (list, tuple)):
            return None

        sorted_periods = sorted(
            [row for row in periods if isinstance(row, dict)],
            key=lambda row: self._parse_iso_date(row.get("start")) or date.max,
        )
        for period in sorted_periods:
            start = self._parse_iso_date(period.get("start"))
            end = self._parse_iso_date(period.get("end"))
            if not start or not end:
                continue
            if start <= target_date <= end:
                return period
        return sorted_periods[-1] if sorted_periods else None

    @staticmethod
    def _build_area_text(area: str) -> str:
        if area == "career":
            return "You achieve success in career."
        if area == "marriage":
            return "You benefit in relationships and partnerships."
        if area == "wealth":
            return "You see growth in wealth and financial stability."
        if area == "health":
            return "You experience important shifts in health and routines."
        if area == "self":
            return "You experience strong personal development."
        if area == "general":
            return "You receive meaningful results in life."
        return f"You receive notable results in {area}."

    @staticmethod
    def _build_strength_text(strength: str) -> str:
        if strength == "strong":
            return "Results are powerful and clearly visible."
        if strength == "weak":
            return "Results are mild and may feel delayed."
        return "Results are moderate and steady."


_default_prediction_service = PredictionService()


def get_prediction(rule_key: Any, language: str | None = None) -> str:
    """Returns a localized prediction meaning for one rule key."""
    return _default_prediction_service.get_prediction(rule_key, language)


def get_prediction_weight(rule_key: Any) -> float:
    """Returns configured prediction weight for one rule key (default 0)."""
    return _default_prediction_service.get_weight(rule_key)


def get_contextual_prediction(
    yoga: Any,
    chart_data: Any,
    language: str | None = None,
) -> Dict[str, str]:
    """Returns context-aware prediction payload for one yoga."""
    return _default_prediction_service.generate_contextual_prediction(yoga, chart_data, language)
