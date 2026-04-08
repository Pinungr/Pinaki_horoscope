from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, TypedDict


AspectRecord = TypedDict(
    "AspectRecord",
    {
        "from": str,
        "to": str,
        "from_house": int,
        "to_house": int,
        "aspect_type": str,
    },
)


DEFAULT_ASPECT_OFFSETS: tuple[int, ...] = (7,)
SPECIAL_ASPECT_OFFSETS: dict[str, tuple[int, ...]] = {
    "Saturn": (3, 7, 10),
    "Jupiter": (5, 7, 9),
    "Mars": (4, 7, 8),
}

# The chart calculator also emits non-planet rows such as Ascendant.
# Only grahas are considered valid drishti sources here.
SUPPORTED_PLANETS: frozenset[str] = frozenset(
    {
        "Sun",
        "Moon",
        "Mars",
        "Mercury",
        "Jupiter",
        "Venus",
        "Saturn",
        "Rahu",
        "Ketu",
    }
)


def calculate_aspects(chart_data: Iterable[object]) -> list[AspectRecord]:
    """
    Calculate Parashara drishti relationships between planets in a chart.

    The function accepts ChartData-like objects or dictionaries that expose
    planet name and house values. Returned records are plain dictionaries so
    they can be passed directly into downstream rule processing.
    """
    normalized_chart = _normalize_chart_data(chart_data)
    aspects: list[AspectRecord] = []

    for source in normalized_chart:
        source_planet = source["planet_name"]
        source_house = source["house"]

        if source_planet not in SUPPORTED_PLANETS:
            continue

        for aspect_offset in _get_aspect_offsets(source_planet):
            target_house = _resolve_aspected_house(source_house, aspect_offset)

            for target in normalized_chart:
                if target["planet_name"] not in SUPPORTED_PLANETS:
                    continue
                if target["planet_name"] == source_planet:
                    continue
                if target["house"] != target_house:
                    continue

                aspects.append(
                    {
                        "from": source_planet,
                        "to": target["planet_name"],
                        "from_house": source_house,
                        "to_house": target_house,
                        "aspect_type": "drishti",
                    }
                )

    return aspects


def _get_aspect_offsets(planet_name: str) -> tuple[int, ...]:
    return SPECIAL_ASPECT_OFFSETS.get(planet_name, DEFAULT_ASPECT_OFFSETS)


def _resolve_aspected_house(source_house: int, aspect_offset: int) -> int:
    return (source_house + aspect_offset - 2) % 12 + 1


def _normalize_chart_data(chart_data: Iterable[object]) -> list[dict[str, Any]]:
    normalized_chart: list[dict[str, Any]] = []

    for entry in chart_data:
        planet_name = _extract_planet_name(entry)
        house = _extract_house(entry)

        if not planet_name or house is None:
            continue

        normalized_chart.append(
            {
                "planet_name": planet_name,
                "house": house,
            }
        )

    return normalized_chart


def _extract_planet_name(entry: object) -> str | None:
    if isinstance(entry, Mapping):
        raw_planet = entry.get("planet_name", entry.get("planet", entry.get("Planet")))
    else:
        raw_planet = getattr(entry, "planet_name", None)

    if raw_planet is None:
        return None

    planet_name = str(raw_planet).strip()
    return planet_name or None


def _extract_house(entry: object) -> int | None:
    if isinstance(entry, Mapping):
        raw_house = entry.get("house", entry.get("House"))
    else:
        raw_house = getattr(entry, "house", None)

    try:
        house = int(raw_house) if raw_house is not None else None
    except (TypeError, ValueError):
        return None

    if house is None or not 1 <= house <= 12:
        return None

    return house
