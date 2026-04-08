from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def normalize_planet_name(planet_name: Any) -> str:
    return str(planet_name or "").strip().lower()


def _coerce_house(raw_house: Any) -> int | None:
    try:
        house = int(raw_house) if raw_house is not None else None
    except (TypeError, ValueError):
        return None

    if house is None or house < 1 or house > 12:
        return None
    return house


def extract_planet_name(item: Any) -> str:
    if isinstance(item, Mapping):
        raw_name = item.get("planet_name", item.get("planet", item.get("Planet")))
    else:
        raw_name = getattr(item, "planet_name", getattr(item, "planet", None))
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
    return _coerce_house(raw_house)


def _is_row_mapping(payload: Mapping[str, Any]) -> bool:
    row_keys = {"planet_name", "planet", "Planet", "house", "House"}
    return any(key in payload for key in row_keys)


def _iter_chart_rows(chart_data: Any) -> Iterable[Any]:
    if chart_data is None:
        return []

    if isinstance(chart_data, Mapping):
        if _is_row_mapping(chart_data):
            return [chart_data]

        rows: list[dict[str, Any]] = []
        for key, value in chart_data.items():
            planet = normalize_planet_name(key)
            if not planet:
                continue

            if isinstance(value, Mapping):
                row = dict(value)
                row.setdefault("planet_name", key)
                rows.append(row)
                continue

            rows.append(
                {
                    "planet_name": key,
                    "house": extract_house(value),
                    "sign": extract_sign(value),
                    "raw": value,
                }
            )
        return rows

    if isinstance(chart_data, Iterable) and not isinstance(chart_data, (str, bytes)):
        return chart_data

    return []


def get_planet_data(chart_data: Any, planet_name: Any) -> dict[str, Any] | None:
    normalized_target = normalize_planet_name(planet_name)
    if not normalized_target:
        return None

    if isinstance(chart_data, Mapping) and not _is_row_mapping(chart_data):
        for key, value in chart_data.items():
            if normalize_planet_name(key) != normalized_target:
                continue
            house = extract_house(value)
            if house is None and isinstance(value, Mapping):
                house = _coerce_house(value.get("house", value.get("House")))
            return {
                "planet_name": normalized_target,
                "sign": extract_sign(value),
                "house": house,
                "raw": value,
            }

    for row in _iter_chart_rows(chart_data):
        current_name = extract_planet_name(row)
        if current_name != normalized_target:
            continue
        return {
            "planet_name": current_name,
            "sign": extract_sign(row),
            "house": extract_house(row),
            "raw": row,
        }

    target_attr = str(planet_name or "").strip()
    for attr_name in (normalized_target, target_attr):
        if not attr_name:
            continue
        planet_obj = getattr(chart_data, attr_name, None)
        if planet_obj is None:
            continue
        return {
            "planet_name": normalized_target,
            "sign": extract_sign(planet_obj),
            "house": extract_house(planet_obj),
            "raw": planet_obj,
        }

    return None


def get_planet_house(chart_data: Any, planet_name: Any) -> int | None:
    planet = get_planet_data(chart_data, planet_name)
    if not planet:
        return None
    return _coerce_house(planet.get("house"))

