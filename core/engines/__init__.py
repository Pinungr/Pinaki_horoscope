"""Reusable business engines for astrology calculations."""

from .aspect_engine import calculate_aspects

__all__ = ["calculate_aspects", "PlanetStrength", "StrengthEngine"]


def __getattr__(name: str):
    if name in {"PlanetStrength", "StrengthEngine"}:
        from .strength_engine import PlanetStrength, StrengthEngine

        return {"PlanetStrength": PlanetStrength, "StrengthEngine": StrengthEngine}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
