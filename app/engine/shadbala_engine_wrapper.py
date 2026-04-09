import logging
from typing import Dict, Any, List, Iterable
from core.yoga.models import ChartSnapshot
from core.engines.shadbala.shadbala_aggregator import ShadbalaEngine
from app.models.domain import ChartData

logger = logging.getLogger(__name__)

_EXCLUDED_POINTS = {"ascendant", "lagna"}
_REQUIRED_COMPONENT_FIELDS = (
    "sthana_bala",
    "dik_bala",
    "kala_bala",
    "chestha_bala",
    "naisargika_bala",
    "drik_bala",
)


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _default_planet_payload(planet: str) -> Dict[str, Any]:
    payload = {"planet": str(planet).strip().lower() or "unknown"}
    for field in _REQUIRED_COMPONENT_FIELDS:
        payload[field] = 0.0
    payload["is_vargottama"] = False
    payload["total"] = 0.0
    return payload


def _normalize_planet_payload(planet: str, raw_payload: Dict[str, Any] | None) -> Dict[str, Any]:
    normalized = _default_planet_payload(planet)
    payload = raw_payload if isinstance(raw_payload, dict) else {}

    for field in _REQUIRED_COMPONENT_FIELDS:
        normalized[field] = round(_safe_float(payload.get(field)), 2)

    normalized["is_vargottama"] = bool(payload.get("is_vargottama", False))
    normalized["total"] = round(sum(_safe_float(normalized[field]) for field in _REQUIRED_COMPONENT_FIELDS), 2)
    normalized["planet"] = str(payload.get("planet", normalized["planet"])).strip().lower() or normalized["planet"]
    return normalized


def normalize_shadbala_payload(
    raw_payload: Dict[str, Any] | None,
    chart_data_models: Iterable[ChartData] | None = None,
) -> Dict[str, Any]:
    """
    Normalizes Shadbala output so every included planet has a stable field set.
    Returns an empty dictionary when no target planets can be inferred.
    """
    payload = raw_payload if isinstance(raw_payload, dict) else {}
    target_planets: list[str] = []

    if chart_data_models is not None:
        snapshot = ChartSnapshot.from_rows(chart_data_models)
        for planet_id in snapshot.placements.keys():
            normalized_id = str(planet_id).strip().lower()
            if not normalized_id or normalized_id in _EXCLUDED_POINTS or normalized_id in target_planets:
                continue
            target_planets.append(normalized_id)

    for raw_planet in payload.keys():
        normalized_id = str(raw_planet).strip().lower()
        if not normalized_id or normalized_id in _EXCLUDED_POINTS or normalized_id in target_planets:
            continue
        target_planets.append(normalized_id)

    if not target_planets:
        return {}

    return {
        planet_id: _normalize_planet_payload(planet_id, payload.get(planet_id))
        for planet_id in target_planets
    }


def calculate_shadbala(chart_data_models: List[ChartData]) -> Dict[str, Any]:
    """
    Wraps the core ShadbalaEngine to work with application-level ChartData models.
    Returns a dictionary of planetary strengths keyed by planet name.
    """
    snapshot = ChartSnapshot.from_rows(chart_data_models)
    logger.debug("Converting %d rows to ChartSnapshot for Shadbala", len(chart_data_models))
    logger.debug("Snapshot created with %d placements", len(snapshot.placements))

    try:
        # 1. Execute Shadbala Engine
        engine = ShadbalaEngine()
        result = engine.calculate(snapshot)
        
        # 2. Return as normalized dictionary for UI/Cache
        logger.debug("Shadbala calculation completed")
        return normalize_shadbala_payload(result.as_dict(), chart_data_models)
    except Exception as exc:
        logger.error("Shadbala calculation failed: %s", exc, exc_info=True)
        return normalize_shadbala_payload({}, chart_data_models)
