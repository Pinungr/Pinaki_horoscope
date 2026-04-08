from __future__ import annotations

from typing import Any, Iterable

from app.engine.dasha import DashaEngine
from core.engines.strength_engine import StrengthEngine
from core.predictions.aggregation_service import aggregate_predictions
from core.predictions.prediction_service import PredictionService
from core.yoga.models import ChartSnapshot
from core.yoga.yoga_engine import YogaEngine, YogaResult


_ZODIAC_SIGNS = [
    "aries",
    "taurus",
    "gemini",
    "cancer",
    "leo",
    "virgo",
    "libra",
    "scorpio",
    "sagittarius",
    "capricorn",
    "aquarius",
    "pisces",
]


class UnifiedAstrologyEngine:
    """
    Unified orchestration engine for the modular astrology stack.

    This class intentionally avoids implementing astrology logic itself and
    delegates to existing specialized engines/services.
    """

    def __init__(
        self,
        *,
        yoga_engine: YogaEngine | None = None,
        strength_engine: StrengthEngine | None = None,
        dasha_engine: DashaEngine | None = None,
        prediction_service: PredictionService | None = None,
    ) -> None:
        self.yoga_engine = yoga_engine or YogaEngine()
        self.strength_engine = strength_engine or StrengthEngine()
        self.dasha_engine = dasha_engine or DashaEngine()
        self.prediction_service = prediction_service or PredictionService()

    def analyze(
        self,
        chart_data: Iterable[Any],
        *,
        dob: str | None = None,
        language: str = "en",
        include_trace: bool = False,
    ) -> dict[str, Any]:
        chart_snapshot = self._build_chart_snapshot(chart_data)
        normalized_language = str(language or "en").strip().lower() or "en"

        yoga_results = self._detect_yogas(
            chart_snapshot,
            language=normalized_language,
            include_trace=include_trace,
        )
        yoga_payload = [result.as_dict() for result in yoga_results]
        strong_yogas = [item for item in yoga_payload if item.get("strength_level") == "strong"]
        weak_yogas = [item for item in yoga_payload if item.get("strength_level") == "weak"]

        chart_strength = self._score_chart_strength(chart_snapshot)
        dasha_payload = self._get_dasha_information(chart_snapshot, dob)
        final_predictions = self._build_final_predictions(yoga_results, normalized_language)

        return {
            "yogas": yoga_payload,
            "strong_yogas": strong_yogas,
            "weak_yogas": weak_yogas,
            "dasha": dasha_payload,
            "final_predictions": final_predictions,
            "confidence_score": self._compute_confidence_score(yoga_results, chart_strength),
        }

    @staticmethod
    def _build_chart_snapshot(chart_data: Iterable[Any]) -> ChartSnapshot:
        return ChartSnapshot.from_rows(chart_data or [])

    def _detect_yogas(
        self,
        chart_snapshot: ChartSnapshot,
        *,
        language: str,
        include_trace: bool,
    ) -> list[YogaResult]:
        return self.yoga_engine.evaluate(
            chart_snapshot,
            language=language,
            detected_only=True,
            include_trace=include_trace,
        )

    def _score_chart_strength(self, chart_snapshot: ChartSnapshot) -> dict[str, int]:
        per_planet = self.strength_engine.score_chart(chart_snapshot)
        scores = [item.score for item in per_planet.values()]

        if not scores:
            return {"average": 0, "count": 0}

        average_score = round(sum(scores) / len(scores), 2)
        return {"average": average_score, "count": len(scores)}

    def _get_dasha_information(self, chart_snapshot: ChartSnapshot, dob: str | None) -> dict[str, Any]:
        moon_longitude = self._extract_moon_longitude(chart_snapshot)
        if moon_longitude is None or not str(dob or "").strip():
            return {"timeline": [], "moon_longitude": moon_longitude}

        timeline = self.dasha_engine.calculate_dasha(moon_longitude, str(dob))
        return {"timeline": timeline, "moon_longitude": moon_longitude}

    @staticmethod
    def _extract_moon_longitude(chart_snapshot: ChartSnapshot) -> float | None:
        moon = chart_snapshot.get("moon")
        if moon is None:
            return None

        sign_key = str(moon.sign or "").strip().lower()
        if sign_key not in _ZODIAC_SIGNS:
            return None

        sign_index = _ZODIAC_SIGNS.index(sign_key)
        return round((sign_index * 30.0) + float(moon.degree), 6)

    def _build_final_predictions(
        self,
        yoga_results: list[YogaResult],
        language: str,
    ) -> list[dict[str, Any]]:
        rule_keys = [result.id for result in yoga_results if result.id]
        if not rule_keys:
            return []

        # Step 5: resolve localized meaning per detected rule.
        _ = [self.prediction_service.get_prediction(rule_key, language) for rule_key in rule_keys]

        # Step 6: aggregate final prediction output.
        aggregated = aggregate_predictions(rule_keys, language)
        details = aggregated.get("details", [])
        return details if isinstance(details, list) else []

    @staticmethod
    def _compute_confidence_score(
        yoga_results: list[YogaResult],
        chart_strength: dict[str, int],
    ) -> float:
        if not yoga_results:
            return float(chart_strength.get("average", 0))

        yoga_scores = [result.strength_score for result in yoga_results]
        yoga_average = sum(yoga_scores) / len(yoga_scores) if yoga_scores else 0.0
        chart_average = float(chart_strength.get("average", 0))

        blended = (0.7 * yoga_average) + (0.3 * chart_average)
        return round(max(0.0, min(100.0, blended)), 2)


def create_default_unified_engine() -> UnifiedAstrologyEngine:
    """Factory helper for the default production orchestration stack."""
    return UnifiedAstrologyEngine(
        yoga_engine=YogaEngine(),
        strength_engine=StrengthEngine(),
        dasha_engine=DashaEngine(),
        prediction_service=PredictionService(),
    )
