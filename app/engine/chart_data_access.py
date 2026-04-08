from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def normalize_planet_name(planet_name: Any) -> str:
    return str(planet_name or "").strip().lower()


def extract_planet_name(item: Any) -> str:
    if isinstance(item, Mapping):
        raw_name = item.get("planet_name", item.get("planet", item.get("Planet")))
    else:
        raw_name = getattr(item, "planet_name", None)
    return normalize_planet_name(raw_name)


def extract_sign(item: Any) -> str:
    if isinstance(item, Mapping):
        raw_sign = item.get("sign", item.get("Sign"))
    else:
        raw_sign = getattr(item, "sign", None)
    return str(raw_sign or "").strip()


def extract_house(item: Any) -> int | None:
    if isinstance(item, Mapping):
        raw_house = item.get("house", item.get("House"))
    else:
        raw_house = getattr(item, "house", None)

    try:
        house = int(raw_house) if raw_house is not None else None
    except (TypeError, ValueError):
        return None

    return house


def get_planet_data(chart_data: Iterable[Any], planet_name: Any) -> dict[str, Any] | None:
    normalized_target = normalize_planet_name(planet_name)
    if not normalized_target:
        return None

    for item in chart_data or []:
        current_name = extract_planet_name(item)
        if current_name != normalized_target:
            continue

        return {
            "planet_name": current_name,
            "sign": extract_sign(item),
            "house": extract_house(item),
            "raw": item,
        }

    return None


def get_planet_house(chart_data: Iterable[Any], planet_name: Any) -> int | None:
    planet_data = get_planet_data(chart_data, planet_name)
    if not planet_data:
        return None

    house = planet_data.get("house")
    return house if isinstance(house, int) else None
