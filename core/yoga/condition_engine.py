from __future__ import annotations

import logging
from time import perf_counter
from dataclasses import dataclass
from typing import Any, Callable

from core.engines.aspect_engine import calculate_aspects
from core.engines.functional_nature import FunctionalNatureEngine
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
            "house_lord_relation": self._handle_house_lord_relation,
            # Dignity
            "planet_in_dignity": self._handle_planet_in_dignity,
            # Relative-house (from a reference planet)
            "any_planet_in_relative_house": self._handle_any_planet_in_relative_house,
            "no_planet_in_relative_house": self._handle_no_planet_in_relative_house,
            "benefics_in_relative_houses": self._handle_benefics_in_relative_houses,
            # Functional
            "planet_is_functional_benefic": self._handle_planet_functional_status,
            "planet_is_functional_malefic": self._handle_planet_functional_status,
            "planet_is_yogakaraka": self._handle_planet_functional_status,
        }
        self.functional_engine = FunctionalNatureEngine()

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

    def evaluate_condition_with_trace(
        self,
        condition: YogaCondition | dict[str, Any],
        chart: ChartSnapshot,
        *,
        context: ConditionContext | None = None,
        path: str | None = None,
    ) -> tuple[bool, dict[str, Any]]:
        condition_type, params = self._normalize_condition(condition)
        trace_entry: dict[str, Any] = {
            "path": str(path or "").strip(),
            "type": condition_type,
        }

        if not condition_type:
            trace_entry["ok"] = False
            trace_entry["reason"] = "invalid_condition"
            trace_entry["elapsed_ms"] = 0.0
            return False, trace_entry

        handler = self._handlers.get(condition_type)
        if handler is None:
            logger.debug("Unsupported condition type '%s'.", condition_type)
            trace_entry["ok"] = False
            trace_entry["reason"] = "unknown_handler"
            trace_entry["elapsed_ms"] = 0.0
            return False, trace_entry

        evaluation_context = context or ConditionContext(chart)
        started_at = perf_counter()
        try:
            matched = bool(handler(params, chart, evaluation_context))
            trace_entry["ok"] = matched
            trace_entry["reason"] = "matched" if matched else "not_matched"
        except Exception:
            logger.exception("Failed while evaluating condition type '%s'.", condition_type)
            matched = False
            trace_entry["ok"] = False
            trace_entry["reason"] = "handler_error"
        finally:
            trace_entry["elapsed_ms"] = round((perf_counter() - started_at) * 1000, 3)

        return matched, trace_entry

    def evaluate_conditions(
        self,
        conditions: list[YogaCondition | dict[str, Any]] | tuple[YogaCondition | dict[str, Any], ...],
        chart: ChartSnapshot,
        *,
        mode: str = "all",
        context: ConditionContext | None = None,
    ) -> bool:
        if not conditions:
            return False

        normalized_mode = str(mode or "all").strip().lower()
        use_any = normalized_mode == "any"
        evaluation_context = context or ConditionContext(chart)

        results = [
            self.evaluate_condition(condition, chart, context=evaluation_context)
            for condition in conditions
        ]
        return any(results) if use_any else all(results)

    def evaluate_conditions_with_trace(
        self,
        conditions: list[YogaCondition | dict[str, Any]] | tuple[YogaCondition | dict[str, Any], ...],
        chart: ChartSnapshot,
        *,
        mode: str = "all",
        context: ConditionContext | None = None,
        path_prefix: str = "conditions",
    ) -> tuple[bool, list[dict[str, Any]]]:
        if not conditions:
            return False, []

        normalized_mode = str(mode or "all").strip().lower()
        use_any = normalized_mode == "any"
        evaluation_context = context or ConditionContext(chart)

        traces: list[dict[str, Any]] = []
        results: list[bool] = []

        for index, condition in enumerate(conditions):
            matched, trace_entry = self.evaluate_condition_with_trace(
                condition,
                chart,
                context=evaluation_context,
                path=f"{path_prefix}[{index}]",
            )
            traces.append(trace_entry)
            results.append(matched)

        return (any(results) if use_any else all(results)), traces

    @staticmethod
    def _normalize_condition(condition: YogaCondition | dict[str, Any]) -> tuple[str, dict[str, Any]]:
        if isinstance(condition, YogaCondition):
            c_type = str(condition.type or "").strip().lower()
            params = dict(condition.params or {})
            params["__type__"] = c_type
            return c_type, params
        if isinstance(condition, dict):
            c_type = str(condition.get("type", "")).strip().lower()
            params = {str(key): value for key, value in condition.items() if str(key) != "type"}
            params["__type__"] = c_type
            return c_type, params
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

    @staticmethod
    def _handle_house_lord_relation(
        params: dict[str, Any], chart: ChartSnapshot, _: ConditionContext
    ) -> bool:
        """
        Checks that the lord of a given house resides in one or more target houses.

        Config example:
            {"type": "house_lord_relation", "of_house": 7, "in_houses": [1, 4, 7, 10]}

        Resolution order:
          1. Find the sign occupying the given house via the Ascendant offset.
          2. Determine the lord of that sign using SIGN_LORDS.
          3. Confirm the lord is placed in one of the target houses.
        """
        raw_of_house = params.get("of_house")
        try:
            of_house = int(raw_of_house)
        except (TypeError, ValueError):
            logger.debug("house_lord_relation: invalid of_house %r", raw_of_house)
            return False

        if not 1 <= of_house <= 12:
            return False

        target_houses = ConditionEngine._normalize_house_set(
            params.get("in_houses", params.get("in_house"))
        )
        if not target_houses:
            return False

        # Resolve the sign that occupies the requested house.
        # In whole-sign system the ascendant sign is house 1; each subsequent
        # house is the next sign in zodiac order.
        ascendant_placement = chart.get("ascendant") or chart.get("lagna")
        if ascendant_placement is None:
            logger.debug("house_lord_relation: no ascendant found in chart")
            return False

        asc_sign = str(ascendant_placement.sign or "").strip().lower()
        if not asc_sign:
            return False

        zodiac = [
            "aries", "taurus", "gemini", "cancer", "leo", "virgo",
            "libra", "scorpio", "sagittarius", "capricorn", "aquarius", "pisces",
        ]
        try:
            asc_index = zodiac.index(asc_sign)
        except ValueError:
            logger.debug("house_lord_relation: unrecognised ascendant sign %r", asc_sign)
            return False

        target_sign = zodiac[(asc_index + of_house - 1) % 12]
        lord_planet = SIGN_LORDS.get(target_sign)
        if not lord_planet:
            logger.debug("house_lord_relation: no lord for sign %r", target_sign)
            return False

        lord_placement = chart.get(lord_planet)
        if lord_placement is None:
            logger.debug("house_lord_relation: lord %r not found in chart", lord_planet)
            return False

        return lord_placement.house in target_houses

    # ------------------------------------------------------------------
    # Dignity handler
    # ------------------------------------------------------------------

    @staticmethod
    def _handle_planet_in_dignity(params: dict[str, Any], chart: ChartSnapshot, _: ConditionContext) -> bool:
        """
        Checks that a planet is in a specified dignity state.

        Supported dignity values:
          "exalted"         – planet is in its classical exaltation sign
          "own"             – planet is in one of its own signs
          "own_or_exalted"  – either of the above

        Config examples:
            {"type": "planet_in_dignity", "planet": "jupiter", "dignity": "exalted"}
            {"type": "planet_in_dignity", "planet": "saturn",  "dignity": "own_or_exalted"}
        """
        EXALTATION: dict[str, str] = {
            "sun": "aries", "moon": "taurus", "mars": "capricorn",
            "mercury": "virgo", "jupiter": "cancer", "venus": "pisces",
            "saturn": "libra", "rahu": "gemini", "ketu": "sagittarius",
        }
        OWN: dict[str, tuple[str, ...]] = {
            "sun": ("leo",), "moon": ("cancer",),
            "mars": ("aries", "scorpio"), "mercury": ("gemini", "virgo"),
            "jupiter": ("sagittarius", "pisces"), "venus": ("taurus", "libra"),
            "saturn": ("capricorn", "aquarius"),
            "rahu": (), "ketu": (),
        }

        planet_id = normalize_planet_id(params.get("planet"))
        if not planet_id:
            return False

        placement = chart.get(planet_id)
        if placement is None:
            return False

        sign = str(placement.sign or "").strip().lower()
        dignity = str(params.get("dignity", "own_or_exalted")).strip().lower()

        is_exalted = (sign == EXALTATION.get(planet_id, ""))
        is_own = (sign in OWN.get(planet_id, ()))

        if dignity == "exalted":
            return is_exalted
        if dignity == "own":
            return is_own
        if dignity in ("own_or_exalted", "exalted_or_own"):
            return is_exalted or is_own
        return False

    # ------------------------------------------------------------------
    # Relative-house handlers (e.g. planets from Moon)
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_relative_house(reference_house: int, offset: int) -> int:
        """Returns the house that is <offset> steps ahead in a 1-12 circle."""
        # Relative-house counting is inclusive:
        # 1st from reference = same house, 2nd = next house, etc.
        return (reference_house + offset - 2) % 12 + 1

    @staticmethod
    def _handle_any_planet_in_relative_house(
        params: dict[str, Any], chart: ChartSnapshot, _: ConditionContext
    ) -> bool:
        """
        Returns True if any qualifying planet occupies one of the listed
        houses relative to a reference planet.

        Config example (Sunapha Yoga – planets in 2nd from Moon, excluding Sun):
            {
              "type": "any_planet_in_relative_house",
              "from_planet": "moon",
              "relative_houses": [2],
              "exclude": ["sun", "rahu", "ketu"]
            }
        """
        ref_id = normalize_planet_id(params.get("from_planet"))
        if not ref_id:
            return False

        ref_placement = chart.get(ref_id)
        if ref_placement is None:
            return False

        offsets = ConditionEngine._normalize_house_set(
            params.get("relative_houses", params.get("relative_house"))
        )
        if not offsets:
            return False

        exclude = {
            normalize_planet_id(p)
            for p in (params.get("exclude") or [])
            if normalize_planet_id(p)
        }
        exclude.add(ref_id)  # always exclude the reference planet itself

        target_houses = {
            ConditionEngine._resolve_relative_house(ref_placement.house, offset)
            for offset in offsets
        }

        for planet_id, placement in chart.placements.items():
            if planet_id in exclude:
                continue
            if placement.house in target_houses:
                return True

        return False

    @staticmethod
    def _handle_no_planet_in_relative_house(
        params: dict[str, Any], chart: ChartSnapshot, context: ConditionContext
    ) -> bool:
        """
        Returns True when NO qualifying planet occupies the relative houses
        (inverse of any_planet_in_relative_house).

        Config example (Kemadruma Yoga – nothing in 2nd or 12th from Moon):
            {
              "type": "no_planet_in_relative_house",
              "from_planet": "moon",
              "relative_houses": [2, 12],
              "exclude": ["sun", "rahu", "ketu"]
            }
        """
        return not ConditionEngine._handle_any_planet_in_relative_house(
            params, chart, context
        )

    @staticmethod
    def _handle_benefics_in_relative_houses(
        params: dict[str, Any], chart: ChartSnapshot, _: ConditionContext
    ) -> bool:
        """
        Returns True if ALL of the specified benefic planets are each found in
        one of the listed relative houses from a reference planet.

        Config example (Adhi Yoga – Jupiter, Venus, Mercury in 6th/7th/8th from Moon):
            {
              "type": "benefics_in_relative_houses",
              "from_planet": "moon",
              "planets": ["jupiter", "venus", "mercury"],
              "relative_houses": [6, 7, 8],
              "require_all": false
            }

        When require_all is False (default) at least one of the listed planets
        must occupy one of the relative houses.
        When require_all is True every planet in the list must occupy one.
        """
        ref_id = normalize_planet_id(params.get("from_planet"))
        if not ref_id:
            return False

        ref_placement = chart.get(ref_id)
        if ref_placement is None:
            return False

        offsets = ConditionEngine._normalize_house_set(
            params.get("relative_houses", params.get("relative_house"))
        )
        if not offsets:
            return False

        target_hours = {
            ConditionEngine._resolve_relative_house(ref_placement.house, offset)
            for offset in offsets
        }

        benefic_ids = [
            normalize_planet_id(p)
            for p in (params.get("planets") or [])
            if normalize_planet_id(p)
        ]
        if not benefic_ids:
            return False

        require_all = bool(params.get("require_all", False))

        matches = [
            planet_id
            for planet_id in benefic_ids
            if (pl := chart.get(planet_id)) is not None and pl.house in target_hours
        ]

        if require_all:
            return len(matches) == len(benefic_ids)
        return len(matches) >= 1

    def _handle_planet_functional_status(
        self, params: dict[str, Any], chart: ChartSnapshot, _: ConditionContext
    ) -> bool:
        """
        Validates if a planet has a specific functional role for the chart's Lagna.
        Config examples:
            { "type": "planet_is_functional_benefic", "planet": "jupiter" }
            { "type": "planet_is_yogakaraka", "planet": "saturn" }
        """
        planet_id = normalize_planet_id(params.get("planet"))
        condition_type = params.get("__type__") # The engine passes this in normalize_condition
        
        # We need the Lagna sign
        lagna = chart.get("ascendant") or chart.get("lagna")
        if not lagna:
            return False
            
        roles = self.functional_engine.get_planet_roles(lagna.sign)
        status = roles.get(planet_id)
        
        if not status:
            return False
            
        if "benefic" in condition_type:
            return status == "benefic" or status == "yogakaraka"
        if "malefic" in condition_type:
            return status == "malefic"
        if "yogakaraka" in condition_type:
            return status == "yogakaraka"
            
        return False
