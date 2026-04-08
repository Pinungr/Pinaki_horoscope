from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from core.engines.aspect_engine import calculate_aspects
from core.yoga.models import ChartSnapshot, YogaCondition, normalize_planet_id


logger = logging.getLogger(__name__)

KENDRA_HOUSES = {1, 4, 7, 10}
SIGN_LORDS = {
    "aries": "mars",
    "taurus": "venus",
    "gemini": "mercury",
    "cancer": "moon",
    "leo": "sun",
    "virgo": "mercury",
    "libra": "venus",
    "scorpio": "mars",
    "sagittarius": "jupiter",
    "capricorn": "saturn",
    "aquarius": "saturn",
    "pisces": "jupiter",
}
CANONICAL_PLANET_NAMES = {
    "sun": "Sun",
    "moon": "Moon",
    "mars": "Mars",
    "mercury": "Mercury",
    "jupiter": "Jupiter",
    "venus": "Venus",
    "saturn": "Saturn",
    "rahu": "Rahu",
    "ketu": "Ketu",
    "ascendant": "Ascendant",
    "lagna": "Ascendant",
}


@dataclass
class ConditionContext:
    chart: ChartSnapshot
    _aspects: list[dict[str, object]] | None = None

    def get_aspects(self) -> list[dict[str, object]]:
        if self._aspects is not None:
            return self._aspects

        aspect_rows = []
        for placement in self.chart.placements.values():
            canonical_planet = CANONICAL_PLANET_NAMES.get(placement.planet)
            if not canonical_planet:
                continue
            aspect_rows.append(
                {
                    "planet_name": canonical_planet,
                    "house": placement.house,
                }
            )

        self._aspects = calculate_aspects(aspect_rows)
        return self._aspects


ConditionHandler = Callable[[dict[str, Any], ChartSnapshot, ConditionContext], bool]


class ConditionEngine:
    """Config-driven condition evaluator for yoga detection."""

    def __init__(self) -> None:
        self._handlers: dict[str, ConditionHandler] = {
            "conjunction": self._handle_conjunction,
            "kendra_from_moon": self._handle_kendra_from_moon,
            "planet_in_house": self._handle_planet_in_house,
            "mutual_exchange": self._handle_mutual_exchange,
            "aspect_relation": self._handle_aspect_relation,
        }

    def evaluate_condition(
        self,
        condition: YogaCondition | dict[str, Any],
        chart: ChartSnapshot,
        *,
        context: ConditionContext | None = None,
    ) -> bool:
        condition_type, params = self._normalize_condition(condition)
        if not condition_type:
            return False

        handler = self._handlers.get(condition_type)
        if handler is None:
            logger.debug("Unsupported condition type '%s'.", condition_type)
            return False

        evaluation_context = context or ConditionContext(chart)
        try:
            return bool(handler(params, chart, evaluation_context))
        except Exception:
            logger.exception("Failed while evaluating condition type '%s'.", condition_type)
            return False

    def evaluate_conditions(
        self,
        conditions: list[YogaCondition | dict[str, Any]] | tuple[YogaCondition | dict[str, Any], ...],
        chart: ChartSnapshot,
        *,
        mode: str = "all",
    ) -> bool:
        if not conditions:
            return False

        normalized_mode = str(mode or "all").strip().lower()
        use_any = normalized_mode == "any"
        context = ConditionContext(chart)

        results = [self.evaluate_condition(condition, chart, context=context) for condition in conditions]
        return any(results) if use_any else all(results)

    @staticmethod
    def _normalize_condition(condition: YogaCondition | dict[str, Any]) -> tuple[str, dict[str, Any]]:
        if isinstance(condition, YogaCondition):
            return str(condition.type or "").strip().lower(), dict(condition.params or {})
        if isinstance(condition, dict):
            condition_type = str(condition.get("type", "")).strip().lower()
            params = {str(key): value for key, value in condition.items() if str(key) != "type"}
            return condition_type, params
        return "", {}

    @staticmethod
    def _normalize_house_set(raw_houses: Any) -> set[int]:
        if isinstance(raw_houses, (list, tuple, set)):
            values = raw_houses
        else:
            values = [raw_houses]

        house_set: set[int] = set()
        for value in values:
            try:
                house = int(value)
            except (TypeError, ValueError):
                continue
            if 1 <= house <= 12:
                house_set.add(house)
        return house_set

    @staticmethod
    def _normalize_planet_list(raw_planets: Any) -> list[str]:
        if not isinstance(raw_planets, (list, tuple, set)):
            return []

        normalized: list[str] = []
        for planet in raw_planets:
            planet_id = normalize_planet_id(planet)
            if planet_id and planet_id not in normalized:
                normalized.append(planet_id)
        return normalized

    @staticmethod
    def _handle_conjunction(params: dict[str, Any], chart: ChartSnapshot, _: ConditionContext) -> bool:
        planets = ConditionEngine._normalize_planet_list(params.get("planets"))
        if len(planets) < 2:
            return False

        houses: list[int] = []
        for planet in planets:
            placement = chart.get(planet)
            if placement is None:
                return False
            houses.append(placement.house)

        return len(set(houses)) == 1

    @staticmethod
    def _handle_kendra_from_moon(params: dict[str, Any], chart: ChartSnapshot, _: ConditionContext) -> bool:
        target_planet = normalize_planet_id(params.get("planet"))
        if not target_planet:
            return False

        moon = chart.get("moon")
        target = chart.get(target_planet)
        if moon is None or target is None:
            return False

        relative_house = (target.house - moon.house) % 12 + 1
        return relative_house in KENDRA_HOUSES

    @staticmethod
    def _handle_planet_in_house(params: dict[str, Any], chart: ChartSnapshot, _: ConditionContext) -> bool:
        target_planet = normalize_planet_id(params.get("planet"))
        if not target_planet:
            return False

        placement = chart.get(target_planet)
        if placement is None:
            return False

        target_houses = ConditionEngine._normalize_house_set(params.get("houses", params.get("house")))
        if not target_houses:
            return False

        return placement.house in target_houses

    @staticmethod
    def _handle_mutual_exchange(params: dict[str, Any], chart: ChartSnapshot, _: ConditionContext) -> bool:
        planets = ConditionEngine._normalize_planet_list(params.get("planets"))
        if len(planets) != 2:
            first = normalize_planet_id(params.get("planet_a"))
            second = normalize_planet_id(params.get("planet_b"))
            planets = [planet for planet in (first, second) if planet]
        if len(planets) != 2:
            return False

        first_placement = chart.get(planets[0])
        second_placement = chart.get(planets[1])
        if first_placement is None or second_placement is None:
            return False

        first_sign_lord = SIGN_LORDS.get(str(first_placement.sign or "").strip().lower())
        second_sign_lord = SIGN_LORDS.get(str(second_placement.sign or "").strip().lower())
        if not first_sign_lord or not second_sign_lord:
            return False

        return first_sign_lord == planets[1] and second_sign_lord == planets[0]

    @staticmethod
    def _handle_aspect_relation(params: dict[str, Any], chart: ChartSnapshot, context: ConditionContext) -> bool:
        source = normalize_planet_id(params.get("from"))
        target = normalize_planet_id(params.get("to"))
        if not source or not target:
            return False

        aspect_type = str(params.get("aspect_type", "drishti")).strip().lower()
        if not aspect_type:
            return False

        aspects = context.get_aspects()
        if not aspects:
            return False

        for aspect in aspects:
            from_planet = normalize_planet_id(aspect.get("from_planet"))
            to_planet = normalize_planet_id(aspect.get("to_planet"))
            row_aspect_type = str(aspect.get("aspect_type", "")).strip().lower()

            if from_planet == source and to_planet == target and row_aspect_type == aspect_type:
                return True

        return False
