from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

KNOWN_PLANET_IDS = {
    "sun",
    "moon",
    "mars",
    "mercury",
    "jupiter",
    "venus",
    "saturn",
    "rahu",
    "ketu",
    "ascendant",
    "lagna",
}


def normalize_planet_id(value: Any) -> str:
    """Returns a stable lowercase planet identifier for config matching."""
    return str(value or "").strip().lower()


@dataclass(frozen=True)
class PlanetPlacement:
    """Normalized runtime representation of one planet in a chart."""

    planet: str
    sign: str
    house: int
    degree: float = 0.0
    retrograde: bool = False

    @classmethod
    def from_row(cls, row: Any) -> PlanetPlacement | None:
        if isinstance(row, Mapping):
            raw_planet = row.get("planet_name", row.get("planet", row.get("Planet")))
            raw_sign = row.get("sign", row.get("Sign", ""))
            raw_house = row.get("house", row.get("House"))
            raw_degree = row.get("degree", row.get("Degree", 0.0))
            raw_retrograde = row.get("retrograde", row.get("Retrograde", False))
        else:
            raw_planet = getattr(row, "planet_name", getattr(row, "planet", None))
            raw_sign = getattr(row, "sign", "")
            raw_house = getattr(row, "house", None)
            raw_degree = getattr(row, "degree", 0.0)
            raw_retrograde = getattr(row, "retrograde", False)

        planet = normalize_planet_id(raw_planet)
        sign = str(raw_sign or "").strip()
        try:
            house = int(raw_house) if raw_house is not None else None
            degree = float(raw_degree or 0.0)
        except (TypeError, ValueError):
            return None

        if not planet or planet not in KNOWN_PLANET_IDS or house is None or not 1 <= house <= 12:
            return None

        return cls(
            planet=planet,
            sign=sign,
            house=house,
            degree=degree,
            retrograde=bool(raw_retrograde),
        )


@dataclass
class ChartSnapshot:
    """Normalized chart model used by future yoga and condition engines."""

    placements: dict[str, PlanetPlacement] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_rows(
        cls,
        rows: Iterable[Any],
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> ChartSnapshot:
        placements: dict[str, PlanetPlacement] = {}

        for row in rows or []:
            placement = PlanetPlacement.from_row(row)
            if placement is None:
                continue
            placements[placement.planet] = placement

        return cls(placements=placements, metadata=dict(metadata or {}))

    def get(self, planet: str) -> PlanetPlacement | None:
        return self.placements.get(normalize_planet_id(planet))


@dataclass(frozen=True)
class YogaCondition:
    """One config-driven condition entry for a yoga definition."""

    type: str
    params: dict[str, Any]

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> YogaCondition:
        condition_type = str(payload.get("type", "")).strip().lower()
        params = {str(key): value for key, value in payload.items() if str(key) != "type"}
        return cls(type=condition_type, params=params)


@dataclass(frozen=True)
class StrengthRule:
    """Generic strength rule container for future weighted scoring."""

    id: str
    params: dict[str, Any]

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any], index: int) -> StrengthRule:
        rule_id = str(payload.get("id", f"strength_rule_{index}")).strip() or f"strength_rule_{index}"
        params = {str(key): value for key, value in payload.items() if str(key) != "id"}
        return cls(id=rule_id, params=params)


@dataclass(frozen=True)
class LocalizedPrediction:
    """Language-keyed prediction messages for one yoga."""

    texts: dict[str, str]

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> LocalizedPrediction:
        texts = {
            str(language).strip().lower(): str(text).strip()
            for language, text in payload.items()
            if str(language).strip() and str(text).strip()
        }
        return cls(texts=texts)

    def get_text(self, language: str, fallback_language: str = "en") -> str:
        normalized_language = str(language or fallback_language).strip().lower() or fallback_language
        return self.texts.get(normalized_language) or self.texts.get(fallback_language, "")


@dataclass(frozen=True)
class YogaDefinition:
    """Config-driven yoga definition loaded from JSON."""

    id: str
    conditions: tuple[YogaCondition, ...]
    strength_rules: tuple[StrengthRule, ...]
    prediction: LocalizedPrediction

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> YogaDefinition:
        yoga_id = str(payload.get("id", "")).strip()
        conditions = tuple(
            YogaCondition.from_dict(item)
            for item in payload.get("conditions", [])
            if isinstance(item, Mapping)
        )
        strength_rules = tuple(
            StrengthRule.from_dict(item, index)
            for index, item in enumerate(payload.get("strength_rules", []), start=1)
            if isinstance(item, Mapping)
        )
        prediction = LocalizedPrediction.from_dict(payload.get("prediction", {}))

        return cls(
            id=yoga_id,
            conditions=conditions,
            strength_rules=strength_rules,
            prediction=prediction,
        )
