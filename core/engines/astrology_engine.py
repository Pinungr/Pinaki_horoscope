from __future__ import annotations

import re
import logging
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Iterable

from app.engine.dasha import DashaEngine
from app.engine.navamsha import NavamshaEngine
from app.engine.prediction_scorer import (
    compute_final_prediction,
    get_varga_concordance,
    rank_predictions_deterministically,
)
from core.engines.aspect_engine import calculate_aspects
from core.engines.dignity_engine import DignityEngine
from core.engines.functional_nature import FunctionalNatureEngine
from core.engines.strength_engine import COMBUSTION_ORB
from core.engines.strength_engine import StrengthEngine
from core.predictions.aggregation_service import aggregate_context_predictions, aggregate_predictions
from core.predictions.prediction_service import PredictionService
from core.yoga.models import ChartSnapshot
from core.yoga.yoga_engine import YogaEngine, YogaResult
from app.engine.transit_engine import TransitEngine

logger = logging.getLogger(__name__)


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

_NATURAL_MALEFICS = {"sun", "mars", "saturn", "rahu", "ketu"}
_CANONICAL_PLANET_IDS = {
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
_PLANET_FRIENDSHIPS: dict[str, dict[str, set[str]]] = {
    "sun": {"friends": {"moon", "mars", "jupiter"}, "enemies": {"venus", "saturn"}},
    "moon": {"friends": {"sun", "mercury"}, "enemies": set()},
    "mars": {"friends": {"sun", "moon", "jupiter"}, "enemies": {"mercury"}},
    "mercury": {"friends": {"sun", "venus"}, "enemies": {"moon"}},
    "jupiter": {"friends": {"sun", "moon", "mars"}, "enemies": {"mercury", "venus"}},
    "venus": {"friends": {"mercury", "saturn"}, "enemies": {"sun", "moon"}},
    "saturn": {"friends": {"mercury", "venus"}, "enemies": {"sun", "moon", "mars"}},
}
_FUNCTIONAL_ROLE_MULTIPLIERS = {
    "yogakaraka": 1.25,
    "benefic": 1.1,
    "neutral": 1.0,
    "malefic": 0.82,
}
_LORDSHIP_DIGNITY_SCORE = {
    "exalted": 90.0,
    "own": 82.0,
    "friendly": 72.0,
    "neutral": 55.0,
    "enemy": 35.0,
    "debilitated": 20.0,
}


def _build_sign_lord_map() -> dict[str, str]:
    """Builds a sign->lord map using the functional nature engine house logic."""
    functional_engine = FunctionalNatureEngine()
    aries_profile = functional_engine.get_functional_profile("aries")
    house_lords = aries_profile.get("house_lords", {})

    sign_lords: dict[str, str] = {}
    for house in range(1, 13):
        sign = _ZODIAC_SIGNS[house - 1]
        lord = str(house_lords.get(house, "")).strip().lower()
        if lord:
            sign_lords[sign] = lord
    return sign_lords


_SIGN_LORDS = _build_sign_lord_map()


def _to_chart_snapshot(chart_data: Any) -> ChartSnapshot:
    if isinstance(chart_data, ChartSnapshot):
        return chart_data
    return ChartSnapshot.from_rows(chart_data or [])


def resolve_lagna_sign(chart_data: Any, lagna_sign: str | None = None) -> str | None:
    """Resolves normalized Lagna sign from explicit input or chart data."""
    explicit_lagna = str(lagna_sign or "").strip().lower()
    if explicit_lagna in _ZODIAC_SIGNS:
        return explicit_lagna

    snapshot = _to_chart_snapshot(chart_data)
    lagna = snapshot.get("ascendant") or snapshot.get("lagna")
    if lagna is None:
        return None

    resolved = str(lagna.sign or "").strip().lower()
    return resolved if resolved in _ZODIAC_SIGNS else None


def _safe_house(value: Any) -> int | None:
    try:
        house = int(value)
    except (TypeError, ValueError):
        return None
    return house if 1 <= house <= 12 else None


def _safe_degree(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _clamp_score(value: float, minimum: float = -1.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(value)))


def _resolve_longitude(placement: Any) -> float | None:
    if placement is None:
        return None

    sign = str(getattr(placement, "sign", "") or "").strip().lower()
    house_degree = _safe_degree(getattr(placement, "degree", 0.0))
    if sign in _ZODIAC_SIGNS:
        return round((_ZODIAC_SIGNS.index(sign) * 30.0) + house_degree, 6)

    raw = getattr(placement, "absolute_longitude", None)
    try:
        if raw is None:
            return None
        return float(raw)
    except (TypeError, ValueError):
        return None


def _normalize_planet(planet: Any) -> str:
    return str(planet or "").strip().lower()


def _build_aspect_rows(chart_snapshot: ChartSnapshot) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for placement in chart_snapshot.placements.values():
        planet_id = _normalize_planet(getattr(placement, "planet", ""))
        if planet_id not in _CANONICAL_PLANET_IDS:
            continue
        rows.append(
            {
                "planet_name": planet_id,
                "house": getattr(placement, "house", None),
            }
        )
    return rows


def _classify_dignity(planet: str, sign: str) -> str:
    normalized_planet = _normalize_planet(planet)
    normalized_sign = str(sign or "").strip().lower()
    if not normalized_planet or not normalized_sign:
        return "neutral"

    primary = DignityEngine.get_dignity(normalized_planet, normalized_sign)
    if primary != "neutral":
        return primary

    sign_lord = _SIGN_LORDS.get(normalized_sign)
    if not sign_lord:
        return "neutral"

    friendship = _PLANET_FRIENDSHIPS.get(normalized_planet, {"friends": set(), "enemies": set()})
    if sign_lord in friendship["friends"]:
        return "friendly"
    if sign_lord in friendship["enemies"]:
        return "enemy"
    return "neutral"


def _is_combust(planet: str, placement: Any, sun_placement: Any) -> bool:
    normalized_planet = _normalize_planet(planet)
    if normalized_planet == "sun":
        return False

    orb = COMBUSTION_ORB.get(normalized_planet)
    if orb is None:
        return False

    planet_longitude = _resolve_longitude(placement)
    sun_longitude = _resolve_longitude(sun_placement)
    if planet_longitude is None or sun_longitude is None:
        return False

    delta = abs(sun_longitude - planet_longitude)
    shortest_arc = min(delta, 360.0 - delta)
    return shortest_arc <= orb


def _default_house_lord_row(house: int, lord: str) -> dict[str, Any]:
    return {
        "house": house,
        "lord": lord,
        "placement": {
            "house": None,
            "sign": "",
            "degree": None,
            "absolute_longitude": None,
        },
        "dignity": {
            "classification": "neutral",
            "sign_lord": None,
        },
        "affliction_flags": {
            "conjunct_malefic": False,
            "malefic_aspect": False,
            "combust": False,
            "malefic_conjunct_planets": [],
            "malefic_aspecting_planets": [],
            "is_afflicted": False,
        },
    }


def get_house_lord_details(chart_data: Any, lagna_sign: str | None = None) -> dict[int, dict[str, Any]]:
    """
    Returns normalized diagnostics for house lords (1-12) for one chart/Lagna.
    """
    snapshot = _to_chart_snapshot(chart_data)
    resolved_lagna = resolve_lagna_sign(snapshot, lagna_sign=lagna_sign)
    if not resolved_lagna:
        return {
            house: _default_house_lord_row(house, "")
            for house in range(1, 13)
        }

    functional_engine = FunctionalNatureEngine()
    house_lords_raw = functional_engine.get_functional_profile(resolved_lagna).get("house_lords", {})
    house_lords = {
        house: _normalize_planet(house_lords_raw.get(house))
        for house in range(1, 13)
    }

    aspect_rows = _build_aspect_rows(snapshot)
    aspects = calculate_aspects(aspect_rows)
    placements = snapshot.placements
    sun_placement = placements.get("sun")

    details: dict[int, dict[str, Any]] = {}
    for house in range(1, 13):
        lord = house_lords.get(house, "")
        row = _default_house_lord_row(house, lord)
        placement = placements.get(lord) if lord else None

        if placement is None:
            details[house] = row
            continue

        placement_house = _safe_house(getattr(placement, "house", None))
        placement_sign = str(getattr(placement, "sign", "") or "").strip().lower()
        degree = round(_safe_degree(getattr(placement, "degree", 0.0)), 4)
        absolute_longitude = _resolve_longitude(placement)

        dignity = _classify_dignity(lord, placement_sign)
        sign_lord = _SIGN_LORDS.get(placement_sign)

        malefic_conjunct_planets = sorted(
            {
                _normalize_planet(other_planet_id)
                for other_planet_id, other_placement in placements.items()
                if _normalize_planet(other_planet_id) in _NATURAL_MALEFICS
                and _normalize_planet(other_planet_id) != lord
                and _safe_house(getattr(other_placement, "house", None)) == placement_house
            }
        )
        malefic_aspecting_planets = sorted(
            {
                _normalize_planet(aspect.get("from_planet"))
                for aspect in aspects
                if _normalize_planet(aspect.get("to_planet")) == lord
                and _normalize_planet(aspect.get("from_planet")) in _NATURAL_MALEFICS
                and _normalize_planet(aspect.get("from_planet")) != lord
            }
        )
        combust = _is_combust(lord, placement, sun_placement)

        row["placement"] = {
            "house": placement_house,
            "sign": placement_sign,
            "degree": degree,
            "absolute_longitude": round(absolute_longitude, 6) if absolute_longitude is not None else None,
        }
        row["dignity"] = {
            "classification": dignity,
            "sign_lord": sign_lord,
        }
        row["affliction_flags"] = {
            "conjunct_malefic": bool(malefic_conjunct_planets),
            "malefic_aspect": bool(malefic_aspecting_planets),
            "combust": combust,
            "malefic_conjunct_planets": malefic_conjunct_planets,
            "malefic_aspecting_planets": malefic_aspecting_planets,
            "is_afflicted": bool(malefic_conjunct_planets or malefic_aspecting_planets or combust),
        }

        details[house] = row

    return details


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
        functional_nature_engine: FunctionalNatureEngine | None = None,
        dasha_engine: DashaEngine | None = None,
        navamsha_engine: NavamshaEngine | None = None,
        prediction_service: PredictionService | None = None,
        ai_refiner: Any | None = None,
    ) -> None:
        self.yoga_engine = yoga_engine or YogaEngine()
        self.strength_engine = strength_engine or StrengthEngine()
        self.functional_nature_engine = functional_nature_engine or FunctionalNatureEngine()
        self.dasha_engine = dasha_engine or DashaEngine()
        self.navamsha_engine = navamsha_engine or NavamshaEngine()
        self.prediction_service = prediction_service or PredictionService()
        self.transit_engine = TransitEngine()
        self.ai_refiner = ai_refiner

    def analyze(
        self,
        chart_data: Iterable[Any],
        *,
        dob: str | None = None,
        language: str = "en",
        include_trace: bool = False,
        transit_date: str | None = None,
    ) -> dict[str, Any]:
        chart_snapshot = self._build_chart_snapshot(chart_data)
        normalized_language = str(language or "en").strip().lower() or "en"
        functional_nature = self._build_functional_nature_payload(chart_snapshot)
        house_lord_details = self._build_house_lord_details_payload(chart_snapshot)

        yoga_results = self._detect_yogas(
            chart_snapshot,
            language=normalized_language,
            include_trace=include_trace,
        )
        yoga_payload = [result.as_dict() for result in yoga_results]
        strong_yogas = [
            item
            for item in yoga_payload
            if str(item.get("state", "")).strip().lower() == "strong"
            or str(item.get("strength_level", "")).strip().lower() == "strong"
        ]
        weak_yogas = [
            item
            for item in yoga_payload
            if str(item.get("state", "")).strip().lower() in {"weak", "cancelled"}
            or str(item.get("strength_level", "")).strip().lower() == "weak"
        ]

        chart_strength = self._score_chart_strength(chart_snapshot)
        dasha_payload = self._get_dasha_information(chart_snapshot, dob)
        transit_payload = self._analyze_current_transits(chart_snapshot, transit_date)
        final_predictions = self._build_final_predictions(yoga_results, normalized_language)

        return {
            "yogas": yoga_payload,
            "ui_yogas": self._format_yoga_ui_payload(yoga_results, normalized_language),
            "strong_yogas": strong_yogas,
            "weak_yogas": weak_yogas,
            "dasha": dasha_payload,
            "transits": transit_payload,
            "final_predictions": final_predictions,
            "functional_nature": functional_nature,
            "house_lord_details": house_lord_details,
            "confidence_score": self._compute_confidence_score(yoga_results, chart_strength),
        }

    def generate_full_analysis(
        self,
        chart_data: Iterable[Any],
        *,
        dob: str | None = None,
        language: str = "en",
        include_trace: bool = False,
        transit_date: str | None = None,
        tone: str = "professional",
    ) -> dict[str, Any]:
        chart_snapshot = self._build_chart_snapshot(chart_data)
        normalized_language = str(language or "en").strip().lower() or "en"
        functional_nature = self._build_functional_nature_payload(chart_snapshot)
        house_lord_details = self._build_house_lord_details_payload(chart_snapshot)
        yoga_results = self._detect_yogas(
            chart_snapshot,
            language=normalized_language,
            include_trace=include_trace,
        )
        dasha_payload = self._get_dasha_information(chart_snapshot, dob)
        transit_payload = self._analyze_current_transits(chart_snapshot, transit_date)
        navamsha_payload = self._calculate_navamsha(chart_snapshot)
        chart_strength = self._score_chart_strength(chart_snapshot)
        base_strength_score = float(chart_strength.get("average", 0.0))
        per_planet_strength = chart_strength.get("per_planet_strength", {})
        if not isinstance(per_planet_strength, dict):
            per_planet_strength = {}
        scoring_weights = (
            self.prediction_service.get_final_layer_weights()
            if hasattr(self.prediction_service, "get_final_layer_weights")
            else None
        )
        area_karaka_predictions = self.prediction_service.build_bhava_lord_karaka_predictions(
            chart_snapshot,
            language=normalized_language,
            house_lord_details=house_lord_details,
            planet_strength=per_planet_strength,
        )
        area_karaka_status: dict[str, list[dict[str, Any]]] = {}
        if isinstance(area_karaka_predictions, list):
            for area_row in area_karaka_predictions:
                if not isinstance(area_row, dict):
                    continue
                area_key = self.prediction_service.normalize_area_key(area_row.get("category", ""))
                if not area_key:
                    continue
                raw_status = area_row.get("karaka_status", [])
                status_rows: list[dict[str, Any]] = []
                if isinstance(raw_status, list):
                    for status_row in raw_status:
                        if isinstance(status_row, dict):
                            status_rows.append(dict(status_row))
                area_karaka_status[area_key] = status_rows

        enriched_predictions: list[dict[str, Any]] = []
        for yoga in yoga_results:
            base_strength = {
                "level": yoga.strength_level,
                "score": base_strength_score,
            }
            yoga_payload = {
                "id": yoga.id,
                "key_planets": list(yoga.key_planets),
                "state": yoga.state,
                "strength_level": yoga.strength_level,
                "strength_score": yoga.strength_score,
            }
            prediction_context = self.prediction_service.extract_prediction_context(yoga_payload, chart_snapshot)
            house = prediction_context.get("house")
            relevant_houses = []
            try:
                if house is not None:
                    relevant_houses.append(int(house))
            except (TypeError, ValueError):
                pass
            prediction_context["relevant_houses"] = relevant_houses
            prediction_context["yoga_planets"] = list(yoga.key_planets)
            timing = self.prediction_service.evaluate_dasha_relevance(
                {
                    "id": yoga.id,
                    "key_planets": list(yoga.key_planets),
                },
                dasha_payload,
                chart_data=chart_snapshot,
                prediction_context=prediction_context,
            )
            transit_trigger = self.prediction_service.evaluate_transit_trigger(
                {
                    "id": yoga.id,
                    "key_planets": list(yoga.key_planets),
                    "area": prediction_context.get("area", "general"),
                    "house": prediction_context.get("house"),
                },
                transit_payload,
                dasha_relevance=timing,
                prediction_context=prediction_context,
            )
            d1_signal, d1_score, d1_factors = self._evaluate_d1_signal(yoga)
            d9_signal, d9_score, d9_factors = self._evaluate_d9_signal(
                prediction_context=prediction_context,
                navamsha_payload=navamsha_payload,
            )
            d10_signal, d10_score, d10_factors = self._evaluate_d10_signal(timing)
            concordance = get_varga_concordance(
                {
                    "area": prediction_context.get("area", "general"),
                    "d1_signal": d1_signal,
                    "d1_score": d1_score,
                    "d9_signal": d9_signal,
                    "d9_score": d9_score,
                    "d10_signal": d10_signal,
                    "d10_score": d10_score,
                }
            )
            functional_layer = self._evaluate_functional_layer(
                prediction_context=prediction_context,
                functional_nature=functional_nature,
            )
            lordship_layer = self._evaluate_lordship_layer(
                prediction_context=prediction_context,
                house_lord_details=house_lord_details,
            )
            yoga_layer_score = self._evaluate_yoga_layer_score(yoga)
            signal_layers = self._build_signal_layers(
                yoga=yoga,
                prediction_context=prediction_context,
                functional_layer=functional_layer,
                lordship_layer=lordship_layer,
                timing=timing,
                transit_trigger=transit_trigger,
                d1_signal=d1_signal,
                d9_signal=d9_signal,
                d10_signal=d10_signal,
            )
            final_prediction_payload = compute_final_prediction(
                {
                    "prediction": yoga.id,
                    "base_strength": base_strength_score,
                    "functional_weight": functional_layer.get("functional_weight", 1.0),
                    "lordship_score": lordship_layer.get("score", 50.0),
                    "yoga_score": yoga_layer_score,
                    "dasha_activation": timing.get("score_multiplier", 1.0),
                    "transit_modifier": transit_trigger.get("score_multiplier", 1.0),
                    "varga_concordance": concordance.get("concordance_modifier", 1.0),
                    "scoring_weights": scoring_weights,
                    "signal_layers": signal_layers,
                }
            )
            final_score = int(final_prediction_payload.get("final_score", 0))
            score_components = final_prediction_payload.get("score_components", {})
            if not isinstance(score_components, dict):
                score_components = {}
            temporal_score = score_components.get("temporal", {})
            if not isinstance(temporal_score, dict):
                temporal_score = {}
            layer_trace = final_prediction_payload.get("trace", {})
            if not isinstance(layer_trace, dict):
                layer_trace = {}
            context_prediction = self.prediction_service.generate_contextual(
                chart=chart_snapshot,
                yoga=yoga_payload,
                strength={**base_strength, "score": final_score},
                language=normalized_language,
            )
            timing_text = self.prediction_service.build_timing_text(timing, language=normalized_language)
            transit_text = self.prediction_service.build_transit_trigger_text(
                transit_trigger,
                area=context_prediction.get("area", "general"),
                timing=timing,
            )
            base_text = str(context_prediction.get("text", "")).strip()
            text = " ".join(part for part in [base_text, timing_text, transit_text] if part).strip()
            prediction_area = context_prediction.get("area", "general")
            prediction_area_key = self.prediction_service.normalize_area_key(prediction_area)
            karaka_status_rows = [
                dict(row)
                for row in area_karaka_status.get(prediction_area_key, [])
                if isinstance(row, dict)
            ]

            activation_trace: list[str] = []
            dedupe_trace = layer_trace.get("deduplication", {}) if isinstance(layer_trace, dict) else {}
            dedupe_summary = dedupe_trace.get("summary", []) if isinstance(dedupe_trace, dict) else []
            if isinstance(dedupe_summary, list):
                activation_trace.extend(
                    str(item).strip() for item in dedupe_summary if str(item).strip()
                )
            dasha_evidence = timing.get("dasha_evidence", [])
            if isinstance(dasha_evidence, list):
                activation_trace.extend(str(item).strip() for item in dasha_evidence if str(item).strip())
            source_factors = transit_trigger.get("source_factors", [])
            if isinstance(source_factors, list):
                activation_trace.extend(str(item).strip() for item in source_factors if str(item).strip())
            concordance_factors = concordance.get("contributing_factors", [])
            if isinstance(concordance_factors, list):
                activation_trace.extend(
                    str(item).strip() for item in concordance_factors if str(item).strip()
                )
            activation_trace.extend(d1_factors)
            activation_trace.extend(d9_factors)
            activation_trace.extend(d10_factors)
            activation_trace.append(
                "Final score = weighted base ({base}) x dasha ({dasha}) x transit ({transit}) x concordance ({concordance}) = {final}.".format(
                    base=score_components.get("weighted_base_score", 0),
                    dasha=temporal_score.get("dasha_activation", 1.0),
                    transit=temporal_score.get("transit_modifier", 1.0),
                    concordance=temporal_score.get("varga_concordance", 1.0),
                    final=final_score,
                )
            )
            functional_trace = functional_layer.get("trace", [])
            if isinstance(functional_trace, list):
                activation_trace.extend(str(item).strip() for item in functional_trace if str(item).strip())
            lordship_trace = lordship_layer.get("trace", [])
            if isinstance(lordship_trace, list):
                activation_trace.extend(str(item).strip() for item in lordship_trace if str(item).strip())
            activation_trace.append(
                "M8 layer inputs => strength: {strength}, functional: {functional}, lordship: {lordship}, yoga: {yoga}.".format(
                    strength=round(base_strength_score, 2),
                    functional=round(float(functional_layer.get("functional_weight", 1.0)), 3),
                    lordship=round(float(lordship_layer.get("score", 50.0)), 2),
                    yoga=round(yoga_layer_score, 2),
                )
            )

            enriched_predictions.append(
                {
                    "yoga": _humanize_yoga_name(yoga.id),
                    "area": context_prediction.get("area", "general"),
                    "state": yoga.state,
                    "strength": yoga.strength_level,
                    "score": final_score,
                    "final_score": final_score,
                    "base_score": score_components.get("weighted_base_score", 0),
                    "strength_score": round(base_strength_score, 2),
                    "functional_weight": round(float(functional_layer.get("functional_weight", 1.0)), 3),
                    "lordship_score": round(float(lordship_layer.get("score", 50.0)), 2),
                    "yoga_score": round(yoga_layer_score, 2),
                    "text": text,
                    "prediction": text,
                    "karaka_status": karaka_status_rows,
                    "trace": layer_trace,
                    "signal_layers": signal_layers,
                    "timing": {
                        "mahadasha": timing.get("mahadasha"),
                        "antardasha": timing.get("antardasha"),
                        "relevance": timing.get("relevance", "low"),
                        "activation_level": timing.get("activation_level", timing.get("relevance", "low")),
                        "activation_score": timing.get("activation_score", 0.0),
                        "matched_planets": timing.get("matched_planets", []),
                    },
                    "dasha_activation": temporal_score.get("dasha_activation", 1.0),
                    "transit_modifier": temporal_score.get("transit_modifier", 1.0),
                    "concordance_score": concordance.get("concordance_score", 0.5),
                    "agreement_level": concordance.get("agreement_level", "medium"),
                    "concordance_factors": concordance_factors if isinstance(concordance_factors, list) else [],
                    "varga_concordance": temporal_score.get("varga_concordance", 1.0),
                    "transit": {
                        "support_state": transit_trigger.get("support_state", "neutral"),
                        "trigger_level": transit_trigger.get("trigger_level", "low"),
                        "trigger_now": bool(transit_trigger.get("trigger_now", False)),
                        "matched_planets": transit_trigger.get("matched_planets", []),
                        "source_factors": transit_trigger.get("source_factors", []),
                    },
                    "activation_trace": activation_trace[:16],
                    "language": normalized_language,
                }
            )

        final_output = aggregate_context_predictions(enriched_predictions)
        refined_predictions = self._refine_predictions(
            final_output.get("predictions", []),
            final_output.get("summary", {}),
            tone=tone,
            language=normalized_language,
        )
        ranked_predictions = rank_predictions_deterministically(refined_predictions)
        final_output["predictions"] = ranked_predictions
        final_output["summary"] = self._rebuild_summary_payload(
            ranked_predictions,
            existing_summary=final_output.get("summary", {}),
        )
        final_output["meta"] = self._rebuild_deterministic_meta(
            chart_snapshot=chart_snapshot,
            predictions=ranked_predictions,
            existing_meta=final_output.get("meta", {}),
            transit_date=transit_date,
        )
        final_output["functional_nature"] = functional_nature
        final_output["house_lord_details"] = house_lord_details
        final_output["ui_yogas"] = self._format_yoga_ui_payload(yoga_results, normalized_language)
        final_output["transits"] = transit_payload
        return final_output

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

    def _format_yoga_ui_payload(
        self,
        yoga_results: list[YogaResult],
        language: str,
    ) -> dict[str, Any]:
        detected = [r for r in yoga_results if r.detected]
        if not detected:
            if language == "hi":
                return {"summary": "कोई विशिष्ट योग नहीं मिला।", "details": []}
            if language == "or":
                return {"summary": "କୌଣସି ବିଶିଷ୍ଟ ଯୋଗ ମିଳିଲା ନାହିଁ।", "details": []}
            return {"summary": "No specific yogas matched.", "details": []}

        details: list[dict[str, Any]] = []
        for r in detected:
            details.append(
                {
                    "rule": r.id,
                    "text": r.prediction,
                    "explanation": (
                        f"State: {r.state.title()} | "
                        f"Strength Score: {r.strength_score} ({r.strength_level.title()})"
                    ),
                    "weight": round(r.strength_score / 10),
                    "reasoning": list(getattr(r, "reasoning", tuple())),
                }
            )

        details.sort(key=lambda x: x["weight"], reverse=True)

        if language == "hi":
            summary_text = f"{len(detected)} विशिष्ट योग पाए गए, जिनमें {_humanize_yoga_name(details[0]['rule'])} शामिल है।"
        elif language == "or":
            summary_text = f"{len(detected)} ବିଶିଷ୍ଟ ଯୋଗ ମିଳିଲା, ଯେଉଁଥିରେ {_humanize_yoga_name(details[0]['rule'])} ସାମିଲ।"
        else:
            summary_text = f"{len(detected)} specific yogas detected, including {_humanize_yoga_name(details[0]['rule'])}."

        return {
            "summary": summary_text,
            "details": details,
        }

    def _score_chart_strength(self, chart_snapshot: ChartSnapshot) -> dict[str, Any]:
        per_planet = self.strength_engine.score_chart(chart_snapshot)
        scores = [item.score for item in per_planet.values()]
        per_planet_strength: dict[str, dict[str, Any]] = {}
        for planet_id in sorted(per_planet.keys()):
            item = per_planet[planet_id]
            breakdown = item.breakdown if isinstance(item.breakdown, dict) else {}
            per_planet_strength[planet_id] = {
                "planet": planet_id,
                "score": float(item.score),
                "level": str(item.level or "").strip().lower(),
                "total": float(breakdown.get("total", 0.0)),
            }

        if not scores:
            return {"average": 0, "count": 0, "per_planet_strength": per_planet_strength}

        average_score = round(sum(scores) / len(scores), 2)
        return {
            "average": average_score,
            "count": len(scores),
            "per_planet_strength": per_planet_strength,
        }

    def _build_functional_nature_payload(self, chart_snapshot: ChartSnapshot) -> dict[str, Any]:
        lagna_sign = self._resolve_lagna_sign(chart_snapshot)
        if not lagna_sign:
            return self.functional_nature_engine.get_functional_profile("")
        return self.functional_nature_engine.get_functional_profile(lagna_sign)

    def _build_house_lord_details_payload(self, chart_snapshot: ChartSnapshot) -> dict[int, dict[str, Any]]:
        lagna_sign = self._resolve_lagna_sign(chart_snapshot)
        return get_house_lord_details(chart_snapshot, lagna_sign=lagna_sign)

    @staticmethod
    def _resolve_lagna_sign(chart_snapshot: ChartSnapshot) -> str | None:
        return resolve_lagna_sign(chart_snapshot)

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
        chart_strength: dict[str, Any],
    ) -> float:
        if not yoga_results:
            return float(chart_strength.get("average", 0))

        yoga_scores = [result.strength_score for result in yoga_results]
        yoga_average = sum(yoga_scores) / len(yoga_scores) if yoga_scores else 0.0
        chart_average = float(chart_strength.get("average", 0))

        blended = (0.7 * yoga_average) + (0.3 * chart_average)
        return round(max(0.0, min(100.0, blended)), 2)

    def _refine_predictions(
        self,
        predictions: list[dict[str, Any]],
        summary: dict[str, Any],
        *,
        tone: str,
        language: str,
    ) -> list[dict[str, Any]]:
        if self.ai_refiner is not None and hasattr(self.ai_refiner, "refine_predictions"):
            try:
                refined = self.ai_refiner.refine_predictions(
                    predictions,
                    summary,
                    tone=tone,
                    language=language,
                )
                if isinstance(refined, list):
                    return refined
            except TypeError:
                try:
                    refined = self.ai_refiner.refine_predictions(predictions, summary, tone=tone)
                    if isinstance(refined, list):
                        return refined
                except Exception:
                    pass
            except Exception:
                pass

        fallback_rows: list[dict[str, Any]] = []
        for prediction in predictions:
            row = dict(prediction)
            row["refined_text"] = str(row.get("text", "")).strip()
            fallback_rows.append(row)
        return fallback_rows

    def _analyze_current_transits(self, chart: ChartSnapshot, target_date_str: str | None) -> dict[str, Any]:
        """Calculates transits and checks for significant Gochar events."""
        target_time = None
        if target_date_str:
            try:
                target_time = datetime.fromisoformat(target_date_str)
            except (ValueError, TypeError):
                pass
        if target_time is None:
            utc_today = datetime.now(timezone.utc).date()
            target_time = datetime(
                utc_today.year,
                utc_today.month,
                utc_today.day,
                tzinfo=timezone.utc,
            )

        # Dual-reference gochar output (Lagna + Chandra Lagna) with shared core computation.
        transit_data = self.transit_engine.calculate_transits(chart, target_time, reference="both")

        # Simple rule matcher for transits (can be expanded into its own engine).
        import json
        import os
        rules_path = os.path.join(os.path.dirname(__file__), "..", "..", "core", "predictions", "transit_rules.json")

        active_from_moon: list[dict[str, Any]] = []
        active_from_lagna: list[dict[str, Any]] = []
        try:
            with open(rules_path, "r") as f:
                rules = json.load(f).get("transit_rules", [])

            from_moon_rows = transit_data.get("from_moon", {}) if isinstance(transit_data, dict) else {}
            from_lagna_rows = transit_data.get("from_lagna", {}) if isinstance(transit_data, dict) else {}

            active_from_moon = self._collect_transit_interpretations(
                rows=from_moon_rows,
                rules=rules,
                reference_key="from_moon",
            )
            active_from_lagna = self._collect_transit_interpretations(
                rows=from_lagna_rows,
                rules=rules,
                reference_key="from_lagna",
            )
        except Exception as e:
            logger.error("Failed to load or process transit rules: %s", e)

        # Backward compatibility:
        # - `interpretations` retains moon-based list
        # - `interpretations_by_reference` exposes separated lagna/moon tracks
        transit_data["interpretations"] = active_from_moon
        transit_data["interpretations_by_reference"] = {
            "from_moon": active_from_moon,
            "from_lagna": active_from_lagna,
        }
        return transit_data

    def _calculate_navamsha(self, chart_snapshot: ChartSnapshot) -> dict[str, dict[str, str]]:
        rows: list[dict[str, Any]] = []
        for placement in chart_snapshot.placements.values():
            if not placement.sign:
                continue
            rows.append(
                {
                    "planet_name": placement.planet.capitalize(),
                    "sign": placement.sign,
                    "degree": placement.degree,
                }
            )

        raw = self.navamsha_engine.calculate_navamsha(rows) if rows else {}
        if not isinstance(raw, dict):
            return {}

        normalized: dict[str, dict[str, str]] = {}
        for planet, payload in raw.items():
            planet_id = str(planet or "").strip().lower()
            if not planet_id or not isinstance(payload, dict):
                continue
            navamsha_sign = str(payload.get("navamsha_sign", "")).strip().lower()
            if not navamsha_sign:
                continue
            normalized[planet_id] = {"navamsha_sign": navamsha_sign}
        return normalized

    def _evaluate_d1_signal(self, yoga: YogaResult) -> tuple[str, float, list[str]]:
        state = str(getattr(yoga, "state", "strong") or "strong").strip().lower()
        strength_level = str(getattr(yoga, "strength_level", "medium") or "medium").strip().lower()
        strength_score = float(getattr(yoga, "strength_score", 0.0) or 0.0)

        score = 0.0
        if state in {"strong", "active", "formed"}:
            score += 0.6
        elif state in {"weak", "cancelled"}:
            score -= 0.5

        if strength_level == "strong":
            score += 0.3
        elif strength_level == "weak":
            score -= 0.3

        if strength_score >= 75:
            score += 0.2
        elif strength_score < 45:
            score -= 0.2

        score = _clamp_score(score)
        if score >= 0.2:
            signal = "support"
        elif score <= -0.2:
            signal = "conflict"
        else:
            signal = "neutral"

        factors = [
            f"D1 signal: yoga state {state} with {strength_level} strength ({round(strength_score, 1)})."
        ]
        return signal, round(score, 3), factors

    def _evaluate_d9_signal(
        self,
        *,
        prediction_context: dict[str, Any],
        navamsha_payload: dict[str, dict[str, str]],
    ) -> tuple[str, float, list[str]]:
        if not isinstance(navamsha_payload, dict) or not navamsha_payload:
            return "neutral", 0.0, ["D9 contribution is neutral or missing."]

        actors: list[str] = []
        for source in (
            prediction_context.get("yoga_planets", []),
            prediction_context.get("karakas", []),
            [prediction_context.get("house_lord")] if prediction_context.get("house_lord") else [],
        ):
            if isinstance(source, list):
                for item in source:
                    normalized = _normalize_planet(item)
                    if normalized and normalized not in actors:
                        actors.append(normalized)
        if not actors:
            return "neutral", 0.0, ["D9 contribution is neutral for this area."]

        strong = 0
        weak = 0
        considered = 0
        factors: list[str] = []
        for planet in actors:
            payload = navamsha_payload.get(planet, {})
            if not isinstance(payload, dict):
                continue
            sign = str(payload.get("navamsha_sign", "")).strip().lower()
            if not sign:
                continue
            dignity = DignityEngine.get_dignity(planet, sign)
            considered += 1
            if dignity in {"exalted", "own", "friendly"}:
                strong += 1
                factors.append(f"D9 supports {planet.capitalize()} ({dignity}).")
            elif dignity in {"debilitated", "enemy"}:
                weak += 1
                factors.append(f"D9 weakens {planet.capitalize()} ({dignity}).")
            else:
                factors.append(f"D9 keeps {planet.capitalize()} neutral.")

        if considered == 0:
            return "neutral", 0.0, ["D9 contribution is neutral or missing."]

        score = (strong - weak) / float(considered)
        score = _clamp_score(score)
        if score >= 0.25:
            signal = "support"
        elif score <= -0.25:
            signal = "conflict"
        else:
            signal = "neutral"
        return signal, round(score, 3), factors[:8]

    @staticmethod
    def _evaluate_d10_signal(timing: dict[str, Any]) -> tuple[str, float, list[str]]:
        status = str(timing.get("d10_status", "neutral") if isinstance(timing, dict) else "neutral").strip().lower() or "neutral"
        if status == "confirm":
            signal = "support"
            score = 0.8
        elif status == "conflict":
            signal = "conflict"
            score = -0.8
        else:
            signal = "neutral"
            score = 0.0

        factors_raw = timing.get("d10_evidence", []) if isinstance(timing, dict) else []
        if isinstance(factors_raw, list):
            factors = [str(item).strip() for item in factors_raw if str(item).strip()]
        else:
            factors = []

        if not factors:
            if status == "confirm":
                factors = ["D10 confirms execution potential for this promise."]
            elif status == "conflict":
                factors = ["D10 shows conflict against this promise direction."]
            else:
                factors = ["D10 is neutral for this prediction area."]

        return signal, score, factors[:6]

    def _evaluate_functional_layer(
        self,
        *,
        prediction_context: dict[str, Any],
        functional_nature: dict[str, Any],
    ) -> dict[str, Any]:
        roles_map = functional_nature.get("roles", {}) if isinstance(functional_nature, dict) else {}
        if not isinstance(roles_map, dict):
            roles_map = {}

        actors: list[str] = []
        seen: set[str] = set()
        for source in (
            prediction_context.get("yoga_planets", []),
            prediction_context.get("karakas", []),
        ):
            if isinstance(source, list):
                for raw in source:
                    normalized = _normalize_planet(raw)
                    if normalized and normalized not in seen:
                        seen.add(normalized)
                        actors.append(normalized)

        house_lord = prediction_context.get("house_lord")
        if isinstance(house_lord, dict):
            lord = _normalize_planet(house_lord.get("lord"))
            if lord and lord not in seen:
                seen.add(lord)
                actors.append(lord)
        else:
            lord = _normalize_planet(house_lord)
            if lord and lord not in seen:
                seen.add(lord)
                actors.append(lord)

        if not actors:
            return {
                "functional_weight": 1.0,
                "actors": [],
                "trace": ["M2 functional nature not available for the selected actors; neutral weight 1.0 applied."],
            }

        actor_rows: list[dict[str, Any]] = []
        multipliers: list[float] = []
        for actor in actors:
            role = str(roles_map.get(actor, "neutral")).strip().lower() or "neutral"
            multiplier = _FUNCTIONAL_ROLE_MULTIPLIERS.get(role, 1.0)
            multipliers.append(multiplier)
            actor_rows.append(
                {
                    "planet": actor,
                    "role": role,
                    "multiplier": round(multiplier, 3),
                }
            )

        functional_weight = round(sum(multipliers) / len(multipliers), 3) if multipliers else 1.0
        role_summary = ", ".join(
            f"{row['planet']}={row['role']}({row['multiplier']})"
            for row in actor_rows
        )
        return {
            "functional_weight": functional_weight,
            "actors": actor_rows,
            "trace": [f"M2 functional roles applied: {role_summary}. Aggregate functional weight={functional_weight}."],
        }

    def _evaluate_lordship_layer(
        self,
        *,
        prediction_context: dict[str, Any],
        house_lord_details: dict[int, dict[str, Any]],
    ) -> dict[str, Any]:
        relevant_houses_raw = prediction_context.get("relevant_houses", [])
        relevant_houses: list[int] = []
        if isinstance(relevant_houses_raw, list):
            for raw_house in relevant_houses_raw:
                house = _safe_house(raw_house)
                if house is not None and house not in relevant_houses:
                    relevant_houses.append(house)

        context_house = _safe_house(prediction_context.get("house"))
        if context_house is not None and context_house not in relevant_houses:
            relevant_houses.append(context_house)

        if not relevant_houses:
            return {
                "score": 50.0,
                "houses": [],
                "trace": ["M3 house-lord layer missing relevant house context; neutral score 50 used."],
            }

        house_rows: list[dict[str, Any]] = []
        for house in sorted(relevant_houses):
            row = house_lord_details.get(house, {}) if isinstance(house_lord_details, dict) else {}
            score, explanation = self._evaluate_house_lord_layer_row(house=house, row=row)
            lord = ""
            if isinstance(row, dict):
                lord = _normalize_planet(row.get("lord"))
            house_rows.append(
                {
                    "house": house,
                    "lord": lord,
                    "score": score,
                    "explanation": explanation,
                }
            )

        average_score = round(
            sum(float(item["score"]) for item in house_rows) / len(house_rows),
            2,
        )
        trace = [f"M3 lordship score aggregated across houses {sorted(relevant_houses)} => {average_score}."]
        trace.extend(str(item["explanation"]) for item in house_rows)
        return {
            "score": average_score,
            "houses": house_rows,
            "trace": trace[:8],
        }

    def _evaluate_house_lord_layer_row(
        self,
        *,
        house: int,
        row: dict[str, Any],
    ) -> tuple[float, str]:
        if not isinstance(row, dict):
            return 50.0, f"House {house}: missing diagnostics, neutral lordship score 50 applied."

        lord = str(row.get("lord", "")).strip().lower() or "unknown"
        placement = row.get("placement", {}) if isinstance(row.get("placement"), dict) else {}
        dignity_payload = row.get("dignity", {}) if isinstance(row.get("dignity"), dict) else {}
        afflictions = row.get("affliction_flags", {}) if isinstance(row.get("affliction_flags"), dict) else {}

        dignity = str(dignity_payload.get("classification", "neutral")).strip().lower() or "neutral"
        placement_house = _safe_house(placement.get("house"))

        score = _LORDSHIP_DIGNITY_SCORE.get(dignity, 55.0)
        if placement_house in {1, 4, 5, 7, 9, 10, 11}:
            score += 8.0
        elif placement_house in {6, 8, 12}:
            score -= 10.0

        if bool(afflictions.get("conjunct_malefic")):
            score -= 10.0
        if bool(afflictions.get("malefic_aspect")):
            score -= 8.0
        if bool(afflictions.get("combust")):
            score -= 12.0

        final_score = round(max(0.0, min(100.0, score)), 2)
        explanation = (
            f"House {house}: lord {lord} with dignity={dignity}, placement_house={placement_house}, "
            f"afflicted={bool(afflictions.get('is_afflicted', False))} => score {final_score}."
        )
        return final_score, explanation

    @staticmethod
    def _evaluate_yoga_layer_score(yoga: YogaResult) -> float:
        base_strength = max(0.0, min(100.0, float(getattr(yoga, "strength_score", 0.0) or 0.0)))
        state = str(getattr(yoga, "state", "strong") or "strong").strip().lower()
        level = str(getattr(yoga, "strength_level", "medium") or "medium").strip().lower()
        state_multiplier = {
            "strong": 1.0,
            "active": 1.0,
            "formed": 1.0,
            "weak": 0.72,
            "cancelled": 0.58,
        }.get(state, 0.86)
        level_multiplier = {
            "strong": 1.0,
            "medium": 0.85,
            "weak": 0.68,
        }.get(level, 0.85)
        adjusted = base_strength * state_multiplier * level_multiplier
        return round(max(0.0, min(100.0, adjusted)), 2)

    def _build_signal_layers(
        self,
        *,
        yoga: YogaResult,
        prediction_context: dict[str, Any],
        functional_layer: dict[str, Any],
        lordship_layer: dict[str, Any],
        timing: dict[str, Any],
        transit_trigger: dict[str, Any],
        d1_signal: str,
        d9_signal: str,
        d10_signal: str,
    ) -> dict[str, list[dict[str, Any]]]:
        relevant_houses = self._normalize_relevant_houses(prediction_context.get("relevant_houses"))
        primary_house = _safe_house(prediction_context.get("house"))
        if primary_house is None and relevant_houses:
            primary_house = relevant_houses[0]

        signal_layers: dict[str, list[dict[str, Any]]] = {
            "strength": [
                {
                    "planet": "chart",
                    "house": primary_house,
                    "concept_type": "strength",
                }
            ],
            "functional_nature": [],
            "lordship": [],
            "yoga": [],
            "dasha": [],
            "transit": [],
            "varga": [],
        }

        functional_actors = functional_layer.get("actors", []) if isinstance(functional_layer, dict) else []
        if isinstance(functional_actors, list):
            for actor in functional_actors:
                if not isinstance(actor, dict):
                    continue
                planet = _normalize_planet(actor.get("planet"))
                if not planet:
                    continue
                signal_layers["functional_nature"].append(
                    {
                        "planet": planet,
                        "house": primary_house,
                        "concept_type": "functional_nature",
                    }
                )

        lordship_rows = lordship_layer.get("houses", []) if isinstance(lordship_layer, dict) else []
        if isinstance(lordship_rows, list):
            for row in lordship_rows:
                if not isinstance(row, dict):
                    continue
                planet = _normalize_planet(row.get("lord"))
                if not planet:
                    continue
                signal_layers["lordship"].append(
                    {
                        "planet": planet,
                        "house": _safe_house(row.get("house")),
                        "concept_type": "lordship",
                    }
                )

        yoga_planets = self._ordered_planets(getattr(yoga, "key_planets", []))
        yoga_houses = relevant_houses if relevant_houses else ([primary_house] if primary_house is not None else [None])
        for planet in yoga_planets:
            for house in yoga_houses:
                signal_layers["yoga"].append(
                    {
                        "planet": planet,
                        "house": house,
                        "concept_type": "yoga",
                    }
                )

        matched_dasha = self._ordered_planets(timing.get("matched_planets", []) if isinstance(timing, dict) else [])
        if not matched_dasha:
            matched_dasha = self._ordered_planets(
                [
                    timing.get("mahadasha") if isinstance(timing, dict) else None,
                    timing.get("antardasha") if isinstance(timing, dict) else None,
                ]
            )
        for planet in matched_dasha:
            signal_layers["dasha"].append(
                {
                    "planet": planet,
                    "house": primary_house,
                    "concept_type": "dasha",
                }
            )

        dominant_trigger = transit_trigger.get("dominant_trigger", {}) if isinstance(transit_trigger, dict) else {}
        dominant_house = _safe_house(dominant_trigger.get("house")) if isinstance(dominant_trigger, dict) else None
        matched_transit = self._ordered_planets(
            transit_trigger.get("matched_planets", []) if isinstance(transit_trigger, dict) else []
        )
        for planet in matched_transit:
            signal_layers["transit"].append(
                {
                    "planet": planet,
                    "house": dominant_house if dominant_house is not None else primary_house,
                    "concept_type": "transit",
                }
            )

        varga_planets = self._ordered_planets(
            list(yoga_planets)
            + self._ordered_planets(prediction_context.get("karakas", []))
            + self._ordered_planets(
                [
                    prediction_context.get("house_lord", {}).get("lord")
                    if isinstance(prediction_context.get("house_lord"), dict)
                    else prediction_context.get("house_lord")
                ]
            )
        )
        varga_house = primary_house
        if d10_signal == "support" and dominant_house is not None:
            varga_house = dominant_house
        for planet in varga_planets:
            signal_layers["varga"].append(
                {
                    "planet": planet,
                    "house": varga_house,
                    "concept_type": "varga",
                }
            )

        # Preserve deterministic ordering and remove local duplicates without dropping valid signals.
        for layer_name, rows in list(signal_layers.items()):
            signal_layers[layer_name] = self._dedupe_signal_rows(rows)

        # Keep D1/D9/D10 direction in traceable form via placeholder planet token.
        signal_layers["varga"].append(
            {
                "planet": f"varga:{d1_signal}:{d9_signal}:{d10_signal}",
                "house": varga_house,
                "concept_type": "varga",
            }
        )
        return signal_layers

    @staticmethod
    def _normalize_relevant_houses(raw_houses: Any) -> list[int]:
        houses: list[int] = []
        if not isinstance(raw_houses, list):
            return houses
        for raw_house in raw_houses:
            house = _safe_house(raw_house)
            if house is not None and house not in houses:
                houses.append(house)
        return houses

    @staticmethod
    def _ordered_planets(raw_planets: Any) -> list[str]:
        planets: list[str] = []
        if not isinstance(raw_planets, (list, tuple, set)):
            return planets
        iterable = (
            sorted(raw_planets, key=lambda item: str(item))
            if isinstance(raw_planets, set)
            else raw_planets
        )
        for raw_planet in iterable:
            planet = _normalize_planet(raw_planet)
            if planet and planet not in planets:
                planets.append(planet)
        return planets

    @staticmethod
    def _dedupe_signal_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        seen: set[tuple[str, int | None, str]] = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            planet = _normalize_planet(row.get("planet")) or "*"
            house = _safe_house(row.get("house"))
            concept_type = str(row.get("concept_type", "") or "").strip().lower()
            if not concept_type:
                continue
            key = (planet, house, concept_type)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(
                {
                    "planet": planet,
                    "house": house,
                    "concept_type": concept_type,
                }
            )
        return deduped

    @staticmethod
    def _rebuild_summary_payload(
        predictions: list[dict[str, Any]],
        *,
        existing_summary: Any,
    ) -> dict[str, Any]:
        summary = dict(existing_summary) if isinstance(existing_summary, dict) else {}
        top = [row for row in predictions if isinstance(row, dict)][:5]

        top_areas: list[str] = []
        for item in top[:3]:
            area = str(item.get("area", "")).strip().lower()
            if area and area not in top_areas:
                top_areas.append(area)

        time_focus: list[str] = []
        for item in top:
            timing = item.get("timing", {})
            if not isinstance(timing, dict):
                continue
            if str(timing.get("relevance", "")).strip().lower() != "high":
                continue
            area = str(item.get("area", "")).strip().lower()
            if area and area not in time_focus:
                time_focus.append(area)

        confidence_score = 0
        if top:
            confidence_score = int(round(sum(float(item.get("score", 0.0)) for item in top) / len(top)))

        summary["top_areas"] = top_areas
        summary["time_focus"] = time_focus[:3]
        summary["confidence_score"] = confidence_score
        return summary

    def _rebuild_deterministic_meta(
        self,
        *,
        chart_snapshot: ChartSnapshot,
        predictions: list[dict[str, Any]],
        existing_meta: Any,
        transit_date: str | None,
    ) -> dict[str, Any]:
        meta = dict(existing_meta) if isinstance(existing_meta, dict) else {}
        meta["generated_at"] = self._build_deterministic_signature(
            chart_snapshot=chart_snapshot,
            predictions=predictions,
            transit_date=transit_date,
        )
        return meta

    @staticmethod
    def _build_deterministic_signature(
        *,
        chart_snapshot: ChartSnapshot,
        predictions: list[dict[str, Any]],
        transit_date: str | None,
    ) -> str:
        placements: list[dict[str, Any]] = []
        for planet in sorted(chart_snapshot.placements.keys()):
            placement = chart_snapshot.placements.get(planet)
            if placement is None:
                continue
            placements.append(
                {
                    "planet": _normalize_planet(getattr(placement, "planet", planet)),
                    "house": _safe_house(getattr(placement, "house", None)),
                    "sign": str(getattr(placement, "sign", "") or "").strip().lower(),
                    "degree": round(_safe_degree(getattr(placement, "degree", 0.0)), 4),
                }
            )

        prediction_rows: list[dict[str, Any]] = []
        for row in predictions:
            if not isinstance(row, dict):
                continue
            prediction_rows.append(
                {
                    "yoga": str(row.get("yoga", "")).strip().lower(),
                    "area": str(row.get("area", "")).strip().lower(),
                    "score": int(row.get("score", 0) or 0),
                }
            )

        fingerprint_payload = {
            "transit_date": str(transit_date or "").strip(),
            "placements": placements,
            "predictions": prediction_rows,
        }
        fingerprint_json = json.dumps(
            fingerprint_payload,
            sort_keys=True,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(fingerprint_json.encode("utf-8")).hexdigest()[:24]
        return f"deterministic:{digest}"

    @staticmethod
    def _collect_transit_interpretations(
        *,
        rows: Any,
        rules: Any,
        reference_key: str,
    ) -> list[dict[str, Any]]:
        if not isinstance(rows, dict) or not isinstance(rules, list):
            return []

        output: list[dict[str, Any]] = []
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            p_id = str(rule.get("planet", "")).strip().lower()
            if not p_id:
                continue
            matching_transit = rows.get(p_id)
            if not isinstance(matching_transit, dict):
                continue
            relative_houses = rule.get("relative_houses", [])
            if not isinstance(relative_houses, list):
                continue
            house_position = matching_transit.get("house_from_reference")
            if house_position in relative_houses:
                output.append(
                    {
                        "id": rule.get("id"),
                        "planet": p_id,
                        "text": rule.get("prediction", ""),
                        "reference": reference_key,
                        "house_position": house_position,
                    }
                )
        return output

    @staticmethod
    def _apply_timing_multiplier(base_score: Any, multiplier: Any) -> int:
        try:
            score = float(base_score)
        except (TypeError, ValueError):
            score = 0.0

        try:
            factor = float(multiplier)
        except (TypeError, ValueError):
            factor = 1.0

        boosted = score * factor
        return int(round(max(0.0, min(100.0, boosted))))


def create_default_unified_engine(*, ai_refiner: Any | None = None) -> UnifiedAstrologyEngine:
    """Factory helper for the default production orchestration stack."""
    return UnifiedAstrologyEngine(
        yoga_engine=YogaEngine(),
        strength_engine=StrengthEngine(),
        dasha_engine=DashaEngine(),
        prediction_service=PredictionService(),
        ai_refiner=ai_refiner,
    )


def _humanize_yoga_name(yoga_id: str) -> str:
    words = re.sub(r"[_\s]+", " ", str(yoga_id or "").strip()).split()
    return " ".join(word.capitalize() for word in words)
