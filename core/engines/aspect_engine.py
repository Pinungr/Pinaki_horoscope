from __future__ import annotations

from collections.abc import Iterable, Mapping


ASPECT_RULES = {
    "Saturn": (3, 7, 10),
    "Jupiter": (5, 7, 9),
    "Mars": (4, 7, 8),
}

DEFAULT_ASPECTS = (7,)
VALID_PLANETS = {
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


def calculate_aspects(chart_data: Iterable[object]) -> list[dict[str, object]]:
    """
    Returns Parashara drishti relationships in a rule-friendly structure.

    Expected output shape:
    {
        "from_planet": "Saturn",
        "to_planet": "Moon",
        "from_house": 3,
        "to_house": 7,
        "aspect_type": "drishti"
    }
    """
    planets = _normalize_chart_data(chart_data)
    aspects: list[dict[str, object]] = []

    for source in planets:
        from_planet = source["planet_name"]
        from_house = source["house"]

        for aspect_offset in _get_aspect_offsets(from_planet):
            to_house = _get_target_house(from_house, aspect_offset)

            for target in planets:
                to_planet = target["planet_name"]
                if to_planet == from_planet or target["house"] != to_house:
                    continue

                aspects.append(
                    {
                        "from_planet": from_planet,
                        "to_planet": to_planet,
                        "from_house": from_house,
                        "to_house": to_house,
                        "aspect_type": "drishti",
                    }
                )

    return aspects


def _get_aspect_offsets(planet_name: str) -> tuple[int, ...]:
    return ASPECT_RULES.get(planet_name, DEFAULT_ASPECTS)


def _get_target_house(from_house: int, aspect_offset: int) -> int:
    return (from_house + aspect_offset - 2) % 12 + 1


def _normalize_chart_data(chart_data: Iterable[object]) -> list[dict[str, int | str]]:
    normalized: list[dict[str, int | str]] = []

    for item in chart_data:
        planet_name = _extract_planet_name(item)
        house = _extract_house(item)

        if not planet_name or house is None or planet_name not in VALID_PLANETS:
            continue

        normalized.append({"planet_name": planet_name, "house": house})

    return normalized


def _extract_planet_name(item: object) -> str | None:
    if isinstance(item, Mapping):
        raw_planet = item.get("planet_name", item.get("planet", item.get("Planet")))
    else:
        raw_planet = getattr(item, "planet_name", None)

    if raw_planet is None:
        return None

    planet_name = str(raw_planet).strip()
    return planet_name or None


def _extract_house(item: object) -> int | None:
    if isinstance(item, Mapping):
        raw_house = item.get("house", item.get("House"))
    else:
        raw_house = getattr(item, "house", None)

    try:
        house = int(raw_house) if raw_house is not None else None
    except (TypeError, ValueError):
        return None

    if house is None or house < 1 or house > 12:
        return None

    return house
