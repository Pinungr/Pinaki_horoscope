from __future__ import annotations

"""
YogaEngine - Orchestrator (STEP 3)
====================================
Loads one or more yoga config JSON files, evaluates every yoga definition
against a live ChartSnapshot, and returns a ranked list of results enriched
with planetary strength and a localized prediction.

Return shape per yoga
---------------------
{
    "id":              "gajakesari_yoga",
    "detected":        True,
    "state":           "strong",
    "strength_score":  78,
    "strength_level":  "strong",
    "reasoning":       ["..."],
    "prediction":      "Gajakesari Yoga is present: ...",
}
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from app.utils.runtime_paths import resolve_resource
from core.engines.dignity_engine import DignityEngine
from core.engines.functional_nature import FunctionalNatureEngine
from core.engines.strength_engine import COMBUSTION_ORB
from core.engines.strength_engine import PlanetStrength
from core.engines.strength_engine import StrengthEngine
from core.yoga.condition_engine import ConditionContext, ConditionEngine
from core.yoga.models import (
    BhangaRule,
    ChartSnapshot,
    YogaDefinition,
    normalize_planet_id,
)

logger = logging.getLogger(__name__)

# Default directory that houses all yoga JSON config files
_DEFAULT_YOGA_CONFIG_DIR = resolve_resource("core", "yoga", "configs")
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
_AUSPICIOUS_HOUSES = {1, 4, 5, 7, 9, 10}
_SUPPORTIVE_HOUSES = {2, 3, 11}
_CHALLENGING_HOUSES = {6, 8, 12}
_DEFAULT_STATE_THRESHOLDS: dict[str, float] = {
    "strong": 72.0,
    "formed": 52.0,
    "cancelled_max": 58.0,
    "chart_strong_min": 68.0,
    "cancel_affliction_hits": 3.0,
}


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class YogaResult:
    """
    Immutable result object for one evaluated yoga.

    Attributes
    ----------
    id              : yoga identifier matching the config JSON
    detected        : True if all conditions fired
    state           : "weak" | "formed" | "strong" | "cancelled"
    strength_score  : 0-100 planetary strength driving this yoga
    strength_level  : "weak" | "medium" | "strong"
    prediction      : localized text (empty string when not detected)
    key_planets     : planet ids used to score strength (for logging/UI)
    """

    id: str
    detected: bool
    state: str
    strength_score: int
    strength_level: str
    prediction: str
    key_planets: tuple[str, ...] = field(default_factory=tuple)
    reasoning: tuple[str, ...] = field(default_factory=tuple)
    trace: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    trace_summary: dict[str, int] | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "yoga_name": self.id,
            "detected": self.detected,
            "state": self.state,
            "strength_score": self.strength_score,
            "strength_level": self.strength_level,
            "prediction": self.prediction,
            "key_planets": list(self.key_planets),
            "reasoning": list(self.reasoning),
        }
        if self.trace:
            payload["trace"] = list(self.trace)
        if self.trace_summary is not None:
            payload["trace_summary"] = dict(self.trace_summary)
        return payload


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class YogaEngine:
    """
    Evaluates all configured yogas against a ChartSnapshot.

    Usage
    -----
    ::

        engine = YogaEngine()                  # loads all JSONs from core/yoga/configs/
        results = engine.evaluate(chart, language="hi")

        detected = [r for r in results if r.detected]
        ranked   = sorted(detected, key=lambda r: r.strength_score, reverse=True)
    """

    def __init__(
        self,
        config_dir: Path | None = None,
        extra_definitions: Iterable[YogaDefinition] | None = None,
        strength_engine: StrengthEngine | None = None,
        functional_nature_engine: FunctionalNatureEngine | None = None,
    ) -> None:
        self._condition_engine = ConditionEngine()
        self._strength_engine = strength_engine or StrengthEngine()
        self._functional_nature_engine = functional_nature_engine or FunctionalNatureEngine()

        self._definitions: list[YogaDefinition] = []
        self._load_configs(config_dir or _DEFAULT_YOGA_CONFIG_DIR)

        for defn in extra_definitions or []:
            if isinstance(defn, YogaDefinition):
                self._definitions.append(defn)

        logger.info(
            "YogaEngine initialised with %d yoga definitions.", len(self._definitions)
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        chart: ChartSnapshot,
        *,
        language: str = "en",
        detected_only: bool = False,
        include_trace: bool = False,
    ) -> list[YogaResult]:
        """
        Evaluates every loaded yoga against the given chart.

        Parameters
        ----------
        chart           : normalized ChartSnapshot
        language        : "en" | "hi" | "or" (falls back to English)
        detected_only   : if True, returns only yogas that fired

        Returns
        -------
        List of YogaResult, ordered by strength_score descending for
        detected yogas and unscored (0) for non-detected yogas.
        """
        normalized_lang = str(language or "en").strip().lower() or "en"
        context = ConditionContext(chart)
        chart_strength = self._safe_score_chart(chart)
        chart_strength_score = self._average_chart_strength(chart_strength)
        lagna_sign = self._resolve_lagna_sign(chart)
        functional_roles = self._resolve_functional_roles(lagna_sign)

        detected_results: list[YogaResult] = []
        not_detected: list[YogaResult] = []

        for defn in self._definitions:
            result = self._evaluate_one(
                defn,
                chart,
                context,
                normalized_lang,
                include_trace=include_trace,
                chart_strength=chart_strength,
                chart_strength_score=chart_strength_score,
                functional_roles=functional_roles,
                lagna_sign=lagna_sign,
            )
            if result.detected:
                detected_results.append(result)
            elif not detected_only:
                not_detected.append(result)

        detected_results.sort(key=lambda r: r.strength_score, reverse=True)
        return detected_results + not_detected

    def evaluate_one(
        self,
        yoga_id: str,
        chart: ChartSnapshot,
        *,
        language: str = "en",
        include_trace: bool = False,
    ) -> YogaResult | None:
        """
        Evaluates a single yoga by id.  Returns None if the id is not found.
        """
        norm_id = str(yoga_id or "").strip().lower()
        for defn in self._definitions:
            if defn.id.lower() == norm_id:
                context = ConditionContext(chart)
                chart_strength = self._safe_score_chart(chart)
                chart_strength_score = self._average_chart_strength(chart_strength)
                lagna_sign = self._resolve_lagna_sign(chart)
                functional_roles = self._resolve_functional_roles(lagna_sign)
                return self._evaluate_one(
                    defn,
                    chart,
                    context,
                    language,
                    include_trace=include_trace,
                    chart_strength=chart_strength,
                    chart_strength_score=chart_strength_score,
                    functional_roles=functional_roles,
                    lagna_sign=lagna_sign,
                )
        return None

    @property
    def loaded_yoga_ids(self) -> list[str]:
        """Returns the list of yoga ids currently loaded."""
        return [defn.id for defn in self._definitions]

    # ------------------------------------------------------------------
    # Internal evaluation
    # ------------------------------------------------------------------

    def _evaluate_one(
        self,
        defn: YogaDefinition,
        chart: ChartSnapshot,
        context: ConditionContext,
        language: str,
        *,
        include_trace: bool = False,
        chart_strength: Mapping[str, PlanetStrength] | None = None,
        chart_strength_score: float | None = None,
        functional_roles: Mapping[str, str] | None = None,
        lagna_sign: str | None = None,
    ) -> YogaResult:
        """Evaluates one YogaDefinition and returns a YogaResult."""
        traces: list[dict[str, Any]] = []
        trace_summary: dict[str, int] | None = None
        try:
            # Evaluate all conditions with the shared context so aspect data
            # can be reused and computed only once.
            if include_trace:
                detected, traces = self._condition_engine.evaluate_conditions_with_trace(
                    defn.conditions,
                    chart,
                    context=context,
                )
                trace_summary = self._build_trace_summary(traces)
            else:
                detected = self._condition_engine.evaluate_conditions(
                    defn.conditions,
                    chart,
                    context=context,
                )
        except Exception:
            logger.exception("YogaEngine: error evaluating conditions for %r.", defn.id)
            detected = False

        if not detected:
            return YogaResult(
                id=defn.id,
                detected=False,
                state="weak",
                strength_score=0,
                strength_level="weak",
                prediction="",
                reasoning=("Base yoga conditions did not match.",),
                trace=tuple(traces),
                trace_summary=trace_summary,
            )

        key_planets = self._extract_key_planets(defn)
        base_strength_score, _, key_planet_strengths = self._compute_strength(
            key_planets,
            chart,
            chart_strength=chart_strength,
        )
        house_bonus, house_reason = self._compute_house_placement_bonus(key_planets, chart)
        functional_bonus, functional_reason = self._compute_functional_bonus(
            key_planets,
            functional_roles=functional_roles,
        )
        sthana_bonus, sthana_reason = self._compute_sthana_bonus(key_planet_strengths)
        (
            affliction_penalty,
            affliction_hits,
            severe_affliction,
            affliction_reason,
        ) = self._compute_affliction_penalty(key_planets, chart, context)

        composite_strength = int(
            round(
                max(
                    0.0,
                    min(
                        100.0,
                        float(base_strength_score)
                        + float(house_bonus)
                        + float(functional_bonus)
                        + float(sthana_bonus)
                        + float(affliction_penalty),
                    ),
                )
            )
        )
        thresholds = self._resolve_state_thresholds(defn.state_thresholds)
        resolved_chart_strength = (
            float(chart_strength_score)
            if chart_strength_score is not None
            else self._average_chart_strength(chart_strength or self._safe_score_chart(chart))
        )
        state, state_reason = self._classify_state(
            composite_strength=composite_strength,
            chart_strength_score=resolved_chart_strength,
            affliction_hits=affliction_hits,
            severe_affliction=severe_affliction,
            thresholds=thresholds,
            cancellation_rules=defn.cancellation_rules,
        )
        final_state, bhanga_reason = self._apply_bhanga_layer(
            base_state=state,
            defn=defn,
            chart=chart,
            context=context,
            key_planets=key_planets,
            key_planet_strengths=key_planet_strengths,
            chart_strength=chart_strength,
            lagna_sign=lagna_sign,
        )
        strength_level = self._strength_level_for_state(final_state, composite_strength, thresholds)

        reasoning = [
            f"Base key-planet Shadbala strength averaged {base_strength_score}/100.",
            house_reason,
            functional_reason,
            sthana_reason,
            affliction_reason,
            state_reason,
            bhanga_reason,
        ]
        reasoning = [line for line in reasoning if str(line).strip()]
        prediction = defn.prediction.get_text(language) if defn.prediction.texts else ""

        logger.debug(
            "YogaEngine: %r DETECTED | state=%s | strength=%d (%s) | planets=%s",
            defn.id, final_state, composite_strength, strength_level, key_planets,
        )

        return YogaResult(
            id=defn.id,
            detected=True,
            state=final_state,
            strength_score=composite_strength,
            strength_level=strength_level,
            prediction=prediction,
            key_planets=tuple(key_planets),
            reasoning=tuple(reasoning),
            trace=tuple(traces),
            trace_summary=trace_summary,
        )

    def _compute_strength(
        self,
        key_planets: list[str],
        chart: ChartSnapshot,
        *,
        chart_strength: Mapping[str, PlanetStrength] | None = None,
    ) -> tuple[int, str, dict[str, PlanetStrength]]:
        """
        Averages the StrengthEngine score across all key planets.
        Falls back to 50/medium when no planets are resolvable.
        """
        normalized_key_planets = [
            normalize_planet_id(planet)
            for planet in key_planets
            if normalize_planet_id(planet)
        ]
        normalized_key_planets = list(dict.fromkeys(normalized_key_planets))

        if not normalized_key_planets:
            return 50, "medium", {}

        available_strength = dict(chart_strength or self._safe_score_chart(chart))
        per_planet: dict[str, PlanetStrength] = {}
        scores: list[int] = []
        for planet_id in normalized_key_planets:
            result = available_strength.get(planet_id)
            if result is None:
                result = self._strength_engine.score_planet(planet_id, chart)
                available_strength[planet_id] = result
            per_planet[planet_id] = result
            scores.append(int(result.score))

        if not scores:
            return 50, "medium", per_planet

        avg = round(sum(scores) / len(scores))
        return avg, self._strength_level_for_score(avg), per_planet

    @staticmethod
    def _strength_level_for_score(score: int) -> str:
        if score >= 70:
            return "strong"
        if score >= 40:
            return "medium"
        return "weak"

    @staticmethod
    def _resolve_lagna_sign(chart: ChartSnapshot) -> str | None:
        lagna = chart.get("ascendant") or chart.get("lagna")
        if lagna is None:
            return None
        sign = str(lagna.sign or "").strip().lower()
        return sign if sign in _ZODIAC_SIGNS else None

    def _resolve_functional_roles(self, lagna_sign: str | None) -> dict[str, str]:
        if not lagna_sign:
            return {}
        try:
            roles = self._functional_nature_engine.get_planet_roles(lagna_sign)
        except Exception:
            logger.exception("YogaEngine: failed to resolve functional roles for lagna=%r", lagna_sign)
            return {}
        return {
            normalize_planet_id(planet): str(role or "neutral").strip().lower() or "neutral"
            for planet, role in (roles or {}).items()
            if normalize_planet_id(planet)
        }

    @staticmethod
    def _average_chart_strength(chart_strength: Mapping[str, PlanetStrength]) -> float:
        if not chart_strength:
            return 0.0
        scores = [float(item.score) for item in chart_strength.values() if item is not None]
        if not scores:
            return 0.0
        return round(sum(scores) / len(scores), 2)

    def _safe_score_chart(self, chart: ChartSnapshot) -> dict[str, PlanetStrength]:
        try:
            return self._strength_engine.score_chart(chart)
        except Exception:
            logger.exception("YogaEngine: chart strength scoring failed; using empty strength cache.")
            return {}

    @staticmethod
    def _resolve_state_thresholds(overrides: Mapping[str, Any] | None) -> dict[str, float]:
        thresholds = dict(_DEFAULT_STATE_THRESHOLDS)
        if not isinstance(overrides, Mapping):
            return thresholds

        for key, value in overrides.items():
            normalized_key = str(key or "").strip().lower()
            if normalized_key not in thresholds:
                continue
            try:
                parsed = float(value)
            except (TypeError, ValueError):
                continue
            thresholds[normalized_key] = parsed
        return thresholds

    def _compute_house_placement_bonus(
        self,
        key_planets: list[str],
        chart: ChartSnapshot,
    ) -> tuple[int, str]:
        if not key_planets:
            return 0, "House placement contribution unavailable because no key planets were resolved."

        total = 0.0
        counted = 0
        for planet in key_planets:
            placement = chart.get(planet)
            if placement is None:
                continue
            counted += 1
            if placement.house in _AUSPICIOUS_HOUSES:
                total += 6.0
            elif placement.house in _SUPPORTIVE_HOUSES:
                total += 1.0
            elif placement.house in _CHALLENGING_HOUSES:
                total -= 6.0

        if counted == 0:
            return 0, "House placement contribution was neutral (key planets missing in chart snapshot)."

        bonus = int(round(total / counted))
        if bonus > 0:
            note = f"House placement boosted yoga strength by +{bonus} (key planets in supportive bhavas)."
        elif bonus < 0:
            note = f"House placement reduced yoga strength by {bonus} (key planets in challenging bhavas)."
        else:
            note = "House placement stayed neutral for this yoga."
        return bonus, note

    @staticmethod
    def _compute_functional_bonus(
        key_planets: list[str],
        *,
        functional_roles: Mapping[str, str] | None,
    ) -> tuple[int, str]:
        if not key_planets:
            return 0, "Functional-nature contribution unavailable because no key planets were resolved."
        if not functional_roles:
            return 0, "Functional-nature contribution remained neutral because Lagna-based roles were unavailable."

        role_weights = {
            "yogakaraka": 8.0,
            "benefic": 4.0,
            "neutral": 0.0,
            "malefic": -5.0,
        }
        total = 0.0
        counted = 0
        role_notes: list[str] = []
        for planet in key_planets:
            role = str(functional_roles.get(normalize_planet_id(planet), "neutral")).strip().lower() or "neutral"
            weight = role_weights.get(role, 0.0)
            counted += 1
            total += weight
            role_notes.append(f"{normalize_planet_id(planet)}={role}")

        if counted == 0:
            return 0, "Functional-nature contribution was neutral."

        bonus = int(round(total / counted))
        return bonus, f"Functional role impact ({', '.join(role_notes)}) adjusted score by {bonus}."

    @staticmethod
    def _compute_sthana_bonus(key_strength: Mapping[str, PlanetStrength]) -> tuple[int, str]:
        if not key_strength:
            return 0, "Sthana Bala contribution unavailable (no key-planet strength records)."

        sthana_values: list[float] = []
        for result in key_strength.values():
            breakdown = result.breakdown if isinstance(result.breakdown, dict) else {}
            try:
                sthana_values.append(float(breakdown.get("sthana_bala", 0.0)))
            except (TypeError, ValueError):
                continue

        if not sthana_values:
            return 0, "Sthana Bala contribution unavailable from strength breakdown."

        avg_sthana = round(sum(sthana_values) / len(sthana_values), 2)
        if avg_sthana >= 55:
            bonus = 6
        elif avg_sthana >= 40:
            bonus = 2
        elif avg_sthana >= 28:
            bonus = -2
        else:
            bonus = -6
        return bonus, f"Average Sthana Bala ({avg_sthana}) contributed {bonus} to yoga strength."

    def _compute_affliction_penalty(
        self,
        key_planets: list[str],
        chart: ChartSnapshot,
        context: ConditionContext,
    ) -> tuple[int, int, bool, str]:
        if not key_planets:
            return 0, 0, False, "Affliction analysis skipped because no key planets were resolved."

        aspects = context.get_aspects()
        sun_placement = chart.get("sun")

        total_penalty = 0.0
        total_hits = 0
        afflicted_planets = 0

        for planet_id in key_planets:
            snapshot = self._get_affliction_snapshot(
                planet_id,
                chart=chart,
                aspects=aspects,
                sun_placement=sun_placement,
            )
            hits = int(snapshot["hits"])
            if hits > 0:
                afflicted_planets += 1
            total_hits += hits
            total_penalty += (-8.0 * int(snapshot["conjunction_hit"]))
            total_penalty += (-6.0 * int(snapshot["aspect_hit"]))
            total_penalty += (-7.0 * int(snapshot["combust_hit"]))

        divisor = max(1, len(key_planets))
        penalty = int(round(total_penalty / divisor))
        severe_affliction = bool(total_hits >= max(2, divisor) or afflicted_planets >= 2)
        if total_hits == 0:
            return 0, 0, False, "No major afflictions were found on key planets."

        return (
            penalty,
            total_hits,
            severe_affliction,
            f"Affliction checks found {total_hits} hit(s), applying {penalty} penalty to yoga strength.",
        )

    def _apply_bhanga_layer(
        self,
        *,
        base_state: str,
        defn: YogaDefinition,
        chart: ChartSnapshot,
        context: ConditionContext,
        key_planets: list[str],
        key_planet_strengths: Mapping[str, PlanetStrength],
        chart_strength: Mapping[str, PlanetStrength] | None,
        lagna_sign: str | None,
    ) -> tuple[str, str]:
        if not defn.bhanga_rules:
            return base_state, ""

        cancel_reasons: list[str] = []
        downgrade_reasons: list[str] = []

        for rule in defn.bhanga_rules:
            triggered, reason = self._evaluate_bhanga_rule(
                rule,
                chart=chart,
                context=context,
                key_planets=key_planets,
                key_planet_strengths=key_planet_strengths,
                chart_strength=chart_strength,
                lagna_sign=lagna_sign,
            )
            if not triggered:
                continue
            effect = self._normalize_bhanga_effect(rule.effect)
            if effect == "cancelled":
                cancel_reasons.append(reason)
            else:
                downgrade_reasons.append(reason)

        if cancel_reasons:
            final_state = "cancelled"
            reason = f"Bhanga triggered cancellation: {'; '.join(cancel_reasons)}"
            return final_state, reason

        if downgrade_reasons:
            final_state = base_state if str(base_state).strip().lower() == "cancelled" else "weak"
            reason = f"Bhanga downgraded yoga strength: {'; '.join(downgrade_reasons)}"
            return final_state, reason

        return base_state, ""

    @staticmethod
    def _normalize_bhanga_effect(raw_effect: Any) -> str:
        normalized = str(raw_effect or "downgrade").strip().lower()
        if normalized in {"cancel", "cancelled"}:
            return "cancelled"
        return "weak"

    def _evaluate_bhanga_rule(
        self,
        rule: BhangaRule,
        *,
        chart: ChartSnapshot,
        context: ConditionContext,
        key_planets: list[str],
        key_planet_strengths: Mapping[str, PlanetStrength],
        chart_strength: Mapping[str, PlanetStrength] | None,
        lagna_sign: str | None,
    ) -> tuple[bool, str]:
        rule_type = str(rule.type or "").strip().lower()
        params = dict(rule.params or {})

        if rule_type in {"planet_debilitated", "house_lord_debilitated", "lord_debilitated"}:
            target_planets, house_refs = self._resolve_bhanga_targets(params, key_planets, lagna_sign)
            triggered: list[str] = []
            for planet in target_planets:
                placement = chart.get(planet)
                if placement is None:
                    continue
                sign = str(placement.sign or "").strip().lower()
                if DignityEngine.get_dignity(planet, sign) == "debilitated":
                    triggered.append(self._planet_reference_label(planet, house_refs))
            if not triggered:
                return False, ""
            return True, f"{', '.join(triggered)} is debilitated."

        if rule_type == "house_lord_in_dusthana":
            tracked_houses = self._normalize_house_list(params.get("houses", params.get("house_lords")))
            dusthana_houses = set(self._normalize_house_list(params.get("dusthana_houses", [6, 8, 12])))
            if not tracked_houses or not dusthana_houses:
                return False, ""
            house_lords = self._resolve_house_lords(lagna_sign)
            if not house_lords:
                return False, ""

            triggered: list[str] = []
            for house in tracked_houses:
                lord = normalize_planet_id(house_lords.get(house))
                if not lord:
                    continue
                placement = chart.get(lord)
                if placement is None:
                    continue
                if int(placement.house) in dusthana_houses:
                    triggered.append(f"{self._ordinal(house)} lord ({lord}) in house {int(placement.house)}")
            if not triggered:
                return False, ""
            return True, f"{', '.join(triggered)}."

        if rule_type == "severe_affliction":
            min_hits = int(params.get("min_hits", 2) or 2)
            min_afflicted_planets = int(params.get("min_afflicted_planets", 1) or 1)
            target_planets, house_refs = self._resolve_bhanga_targets(params, key_planets, lagna_sign)
            if not target_planets:
                return False, ""

            aspects = context.get_aspects()
            sun_placement = chart.get("sun")
            total_hits = 0
            afflicted_labels: list[str] = []
            for planet in target_planets:
                snapshot = self._get_affliction_snapshot(
                    planet,
                    chart=chart,
                    aspects=aspects,
                    sun_placement=sun_placement,
                )
                hits = int(snapshot["hits"])
                total_hits += hits
                if hits > 0:
                    afflicted_labels.append(self._planet_reference_label(planet, house_refs))

            if total_hits < min_hits or len(afflicted_labels) < min_afflicted_planets:
                return False, ""
            return True, f"Severe affliction ({total_hits} hit(s)) on {', '.join(afflicted_labels)}."

        if rule_type in {"combustion", "combust"}:
            target_planets, house_refs = self._resolve_bhanga_targets(params, key_planets, lagna_sign)
            if not target_planets:
                return False, ""

            sun_placement = chart.get("sun")
            combusted = [
                self._planet_reference_label(planet, house_refs)
                for planet in target_planets
                if (placement := chart.get(planet)) is not None and self._is_combust(planet, placement, sun_placement)
            ]
            if not combusted:
                return False, ""
            return True, f"Combustion weakens {', '.join(combusted)}."

        if rule_type == "weak_shadbala":
            max_score = float(params.get("max_score", params.get("threshold", 40.0)))
            target_planets, house_refs = self._resolve_bhanga_targets(params, key_planets, lagna_sign)
            if not target_planets:
                return False, ""

            available_strength = dict(chart_strength or self._safe_score_chart(chart))
            weak_targets: list[str] = []
            for planet in target_planets:
                result = key_planet_strengths.get(planet) or available_strength.get(planet)
                if result is None:
                    result = self._strength_engine.score_planet(planet, chart)
                    available_strength[planet] = result
                if float(result.score) <= max_score:
                    weak_targets.append(
                        f"{self._planet_reference_label(planet, house_refs)} ({int(result.score)}/100)"
                    )
            if not weak_targets:
                return False, ""
            return True, f"Weak Shadbala detected for {', '.join(weak_targets)}."

        if rule_type in {"requires_debilitated_planet", "neecha_bhanga_validation"}:
            target_planets, _ = self._resolve_bhanga_targets(params, key_planets, lagna_sign)
            if not target_planets:
                target_planets = [
                    planet_id
                    for planet_id in chart.placements.keys()
                    if planet_id not in {"ascendant", "lagna"}
                ]
            debilitated = [
                planet
                for planet in target_planets
                if (placement := chart.get(planet)) is not None
                and DignityEngine.get_dignity(planet, str(placement.sign or "").strip().lower()) == "debilitated"
            ]
            if debilitated:
                return False, ""
            return True, "No debilitated planet is present to justify Neecha Bhanga."

        return False, ""

    def _resolve_bhanga_targets(
        self,
        params: Mapping[str, Any],
        key_planets: list[str],
        lagna_sign: str | None,
    ) -> tuple[list[str], dict[str, set[int]]]:
        target_planets: list[str] = []
        seen: set[str] = set()
        house_refs: dict[str, set[int]] = {}

        raw_planets = params.get("planets")
        if isinstance(raw_planets, (list, tuple, set)):
            for raw in raw_planets:
                planet_id = normalize_planet_id(raw)
                if planet_id and planet_id not in seen:
                    seen.add(planet_id)
                    target_planets.append(planet_id)
        else:
            planet_id = normalize_planet_id(params.get("planet"))
            if planet_id and planet_id not in seen:
                seen.add(planet_id)
                target_planets.append(planet_id)

        house_lord_houses = self._normalize_house_list(params.get("house_lords", params.get("houses")))
        if house_lord_houses:
            resolved_house_lords = self._resolve_house_lords(lagna_sign)
            for house in house_lord_houses:
                lord = normalize_planet_id(resolved_house_lords.get(house))
                if not lord:
                    continue
                house_refs.setdefault(lord, set()).add(house)
                if lord not in seen:
                    seen.add(lord)
                    target_planets.append(lord)

        use_key_planets = bool(params.get("use_key_planets", not target_planets))
        if use_key_planets:
            for raw in key_planets:
                planet_id = normalize_planet_id(raw)
                if planet_id and planet_id not in seen:
                    seen.add(planet_id)
                    target_planets.append(planet_id)

        return target_planets, house_refs

    def _resolve_house_lords(self, lagna_sign: str | None) -> dict[int, str]:
        if not lagna_sign:
            return {}
        try:
            profile = self._functional_nature_engine.get_functional_profile(lagna_sign)
        except Exception:
            logger.exception("YogaEngine: failed to resolve house lords for lagna=%r", lagna_sign)
            return {}
        raw_house_lords = profile.get("house_lords", {})
        resolved: dict[int, str] = {}
        for key, value in (raw_house_lords or {}).items():
            try:
                house = int(key)
            except (TypeError, ValueError):
                continue
            if not 1 <= house <= 12:
                continue
            planet_id = normalize_planet_id(value)
            if planet_id:
                resolved[house] = planet_id
        return resolved

    @staticmethod
    def _normalize_house_list(raw_value: Any) -> list[int]:
        values = raw_value if isinstance(raw_value, (list, tuple, set)) else [raw_value]
        houses: list[int] = []
        seen: set[int] = set()
        for value in values:
            try:
                house = int(value)
            except (TypeError, ValueError):
                continue
            if not 1 <= house <= 12 or house in seen:
                continue
            seen.add(house)
            houses.append(house)
        return houses

    def _planet_reference_label(self, planet: str, house_refs: Mapping[str, set[int]]) -> str:
        normalized_planet = normalize_planet_id(planet)
        houses = sorted(house_refs.get(normalized_planet, set()))
        if not houses:
            return normalized_planet
        if len(houses) == 1:
            return f"{self._ordinal(houses[0])} lord ({normalized_planet})"
        rendered = ", ".join(str(house) for house in houses)
        return f"lords of houses {rendered} ({normalized_planet})"

    @staticmethod
    def _ordinal(value: int) -> str:
        if 10 <= value % 100 <= 20:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
        return f"{value}{suffix}"

    def _get_affliction_snapshot(
        self,
        planet_id: str,
        *,
        chart: ChartSnapshot,
        aspects: list[dict[str, Any]],
        sun_placement: Any,
    ) -> dict[str, Any]:
        normalized_planet = normalize_planet_id(planet_id)
        placement = chart.get(normalized_planet)
        if placement is None:
            return {
                "hits": 0,
                "conjunction_hit": False,
                "aspect_hit": False,
                "combust_hit": False,
            }

        conjunction_malefics = {
            normalize_planet_id(other_planet_id)
            for other_planet_id, other_placement in chart.placements.items()
            if normalize_planet_id(other_planet_id) in _NATURAL_MALEFICS
            and normalize_planet_id(other_planet_id) != normalized_planet
            and getattr(other_placement, "house", None) == placement.house
        }
        aspect_malefics = {
            normalize_planet_id(aspect.get("from_planet"))
            for aspect in aspects
            if normalize_planet_id(aspect.get("to_planet")) == normalized_planet
            and normalize_planet_id(aspect.get("from_planet")) in _NATURAL_MALEFICS
            and normalize_planet_id(aspect.get("from_planet")) != normalized_planet
        }
        combust_hit = self._is_combust(normalized_planet, placement, sun_placement)

        conjunction_hit = bool(conjunction_malefics)
        aspect_hit = bool(aspect_malefics)
        hits = int(conjunction_hit) + int(aspect_hit) + int(combust_hit)
        return {
            "hits": hits,
            "conjunction_hit": conjunction_hit,
            "aspect_hit": aspect_hit,
            "combust_hit": bool(combust_hit),
        }

    @staticmethod
    def _resolve_longitude(placement: Any) -> float | None:
        if placement is None:
            return None

        sign = str(getattr(placement, "sign", "") or "").strip().lower()
        degree = getattr(placement, "degree", 0.0)
        try:
            degree_value = float(degree)
        except (TypeError, ValueError):
            degree_value = 0.0
        if sign not in _ZODIAC_SIGNS:
            raw_longitude = getattr(placement, "absolute_longitude", None)
            try:
                if raw_longitude is not None:
                    return float(raw_longitude)
            except (TypeError, ValueError):
                return None
            return None
        return (_ZODIAC_SIGNS.index(sign) * 30.0) + degree_value

    def _is_combust(self, planet_id: str, placement: Any, sun_placement: Any) -> bool:
        normalized_planet = normalize_planet_id(planet_id)
        if normalized_planet == "sun":
            return False

        orb = COMBUSTION_ORB.get(normalized_planet)
        if orb is None:
            return False

        planet_longitude = self._resolve_longitude(placement)
        sun_longitude = self._resolve_longitude(sun_placement)
        if planet_longitude is None or sun_longitude is None:
            return False

        delta = abs(sun_longitude - planet_longitude)
        shortest_arc = min(delta, 360.0 - delta)
        return shortest_arc <= orb

    @staticmethod
    def _classify_state(
        *,
        composite_strength: int,
        chart_strength_score: float,
        affliction_hits: int,
        severe_affliction: bool,
        thresholds: Mapping[str, float],
        cancellation_rules: Mapping[str, Any] | None,
    ) -> tuple[str, str]:
        cancel_score_max = float(thresholds.get("cancelled_max", 58.0))
        strong_min = float(thresholds.get("strong", 72.0))
        formed_min = float(thresholds.get("formed", 52.0))
        chart_strong_min = float(thresholds.get("chart_strong_min", 68.0))
        cancel_affliction_hits = int(round(float(thresholds.get("cancel_affliction_hits", 3.0))))

        rules = dict(cancellation_rules or {})
        if bool(rules.get("force_cancel", False)):
            return "cancelled", "Yoga marked as cancelled by explicit cancellation rule."

        if rules.get("cancelled_max") is not None:
            try:
                cancel_score_max = float(rules.get("cancelled_max"))
            except (TypeError, ValueError):
                pass
        if rules.get("cancel_affliction_hits") is not None:
            try:
                cancel_affliction_hits = int(rules.get("cancel_affliction_hits"))
            except (TypeError, ValueError):
                pass

        cancel_on_severe_affliction = bool(rules.get("cancel_on_severe_affliction", True))
        if (
            cancel_on_severe_affliction
            and severe_affliction
            and affliction_hits >= cancel_affliction_hits
            and composite_strength <= cancel_score_max
        ):
            return "cancelled", "Yoga is cancelled due to severe afflictions outweighing its formation."

        if composite_strength >= strong_min:
            if chart_strength_score >= chart_strong_min:
                return "strong", "Yoga is strong: key planets are powerful, supported, and chart strength passes the strong gate."
            return "formed", "Yoga is formed but chart-wide strength is below strong threshold, so strong state is blocked."

        if composite_strength >= formed_min:
            return "formed", "Yoga conditions are met with moderate supporting factors."
        return "weak", "Yoga is present but weakened by insufficient planetary support."

    @staticmethod
    def _strength_level_for_state(state: str, score: int, thresholds: Mapping[str, float]) -> str:
        normalized_state = str(state or "").strip().lower()
        if normalized_state == "strong":
            return "strong"
        if normalized_state == "formed":
            return "medium"
        if normalized_state in {"weak", "cancelled"}:
            return "weak"
        return "medium" if score >= float(thresholds.get("formed", 52.0)) else "weak"

    # ------------------------------------------------------------------
    # Key-planet extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_key_planets(defn: YogaDefinition) -> list[str]:
        """
        Extracts the planet ids that are most relevant to this yoga from its
        condition params.  Used to drive the strength calculation.
        """
        planet_ids: list[str] = []
        seen: set[str] = set()

        for condition in defn.conditions:
            params = condition.params or {}

            # Single-planet conditions
            for key in ("planet", "from", "to"):
                raw = params.get(key)
                if raw:
                    pid = normalize_planet_id(raw)
                    if pid and pid not in seen:
                        seen.add(pid)
                        planet_ids.append(pid)

            # Multi-planet list conditions
            for key in ("planets",):
                raw_list = params.get(key)
                if isinstance(raw_list, (list, tuple)):
                    for raw in raw_list:
                        pid = normalize_planet_id(raw)
                        if pid and pid not in seen:
                            seen.add(pid)
                            planet_ids.append(pid)

        for strength_rule in defn.strength_rules:
            params = strength_rule.params or {}
            raw = params.get("planet")
            pid = normalize_planet_id(raw)
            if pid and pid not in seen:
                seen.add(pid)
                planet_ids.append(pid)

        return planet_ids

    @staticmethod
    def _build_trace_summary(traces: list[dict[str, Any]]) -> dict[str, int]:
        passed = sum(1 for trace in traces if bool(trace.get("ok")))
        total = len(traces)
        return {
            "total": total,
            "passed": passed,
            "failed": total - passed,
        }

    # ------------------------------------------------------------------
    # Config loading
    # ------------------------------------------------------------------

    def _load_configs(self, config_dir: Path) -> None:
        """
        Loads all *.json files from *config_dir* as lists of yoga definitions.
        Each JSON file must be a JSON **array** of yoga objects.
        """
        if not config_dir.is_dir():
            logger.warning(
                "YogaEngine: config directory %r does not exist. No yogas loaded.",
                str(config_dir),
            )
            return

        json_files = sorted(config_dir.glob("*.json"))
        if not json_files:
            logger.warning(
                "YogaEngine: no *.json files found in %r.", str(config_dir)
            )
            return

        for json_file in json_files:
            self._load_file(json_file)

    def _load_file(self, json_file: Path) -> None:
        try:
            payload = json.loads(json_file.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("YogaEngine: failed to load %r: %s", str(json_file), exc)
            return

        if not isinstance(payload, list):
            logger.warning(
                "YogaEngine: %r must be a JSON array; skipping.", str(json_file)
            )
            return

        loaded = 0
        for item in payload:
            if not isinstance(item, dict):
                continue
            yoga_id = str(item.get("id", "")).strip()
            if not yoga_id:
                logger.debug("YogaEngine: skipping entry without id in %r.", str(json_file))
                continue
            try:
                defn = YogaDefinition.from_dict(item)
                self._definitions.append(defn)
                loaded += 1
            except Exception as exc:
                logger.warning(
                    "YogaEngine: failed to parse yoga %r in %r: %s",
                    yoga_id, str(json_file), exc,
                )

        logger.debug("YogaEngine: loaded %d yogas from %r.", loaded, str(json_file))
