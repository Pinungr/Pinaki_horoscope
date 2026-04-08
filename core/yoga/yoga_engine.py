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
    "strength_score":  78,
    "strength_level":  "strong",
    "prediction":      "Gajakesari Yoga is present: ...",
}
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from app.utils.runtime_paths import resolve_resource
from core.engines.strength_engine import StrengthEngine
from core.yoga.condition_engine import ConditionContext, ConditionEngine
from core.yoga.models import (
    ChartSnapshot,
    YogaDefinition,
    normalize_planet_id,
)

logger = logging.getLogger(__name__)

# Default directory that houses all yoga JSON config files
_DEFAULT_YOGA_CONFIG_DIR = resolve_resource("core", "yoga", "configs")


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
    strength_score  : 0-100 planetary strength driving this yoga
    strength_level  : "weak" | "medium" | "strong"
    prediction      : localized text (empty string when not detected)
    key_planets     : planet ids used to score strength (for logging/UI)
    """

    id: str
    detected: bool
    strength_score: int
    strength_level: str
    prediction: str
    key_planets: tuple[str, ...] = field(default_factory=tuple)
    trace: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    trace_summary: dict[str, int] | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "detected": self.detected,
            "strength_score": self.strength_score,
            "strength_level": self.strength_level,
            "prediction": self.prediction,
            "key_planets": list(self.key_planets),
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
    ) -> None:
        self._condition_engine = ConditionEngine()
        self._strength_engine = StrengthEngine()

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

        detected_results: list[YogaResult] = []
        not_detected: list[YogaResult] = []

        for defn in self._definitions:
            result = self._evaluate_one(
                defn,
                chart,
                context,
                normalized_lang,
                include_trace=include_trace,
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
                return self._evaluate_one(
                    defn,
                    chart,
                    context,
                    language,
                    include_trace=include_trace,
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
                strength_score=0,
                strength_level="weak",
                prediction="",
                trace=tuple(traces),
                trace_summary=trace_summary,
            )

        key_planets = self._extract_key_planets(defn)
        strength_score, strength_level = self._compute_strength(key_planets, chart, defn)
        prediction = defn.prediction.get_text(language) if defn.prediction.texts else ""

        logger.debug(
            "YogaEngine: %r DETECTED | strength=%d (%s) | planets=%s",
            defn.id, strength_score, strength_level, key_planets,
        )

        return YogaResult(
            id=defn.id,
            detected=True,
            strength_score=strength_score,
            strength_level=strength_level,
            prediction=prediction,
            key_planets=tuple(key_planets),
            trace=tuple(traces),
            trace_summary=trace_summary,
        )

    def _compute_strength(
        self,
        key_planets: list[str],
        chart: ChartSnapshot,
        defn: YogaDefinition,
    ) -> tuple[int, str]:
        """
        Averages the StrengthEngine score across all key planets.
        Falls back to 50/medium when no planets are resolvable.
        """
        if not key_planets:
            return 50, "medium"

        scores: list[int] = []
        for planet_id in key_planets:
            planet_result = self._strength_engine.score_planet(planet_id, chart)
            scores.append(planet_result.score)

        avg = round(sum(scores) / len(scores))

        if avg >= 70:
            level = "strong"
        elif avg >= 40:
            level = "medium"
        else:
            level = "weak"

        return avg, level

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
            payload = json.loads(json_file.read_text(encoding="utf-8"))
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
