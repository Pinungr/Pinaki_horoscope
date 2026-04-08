"""Core data structures for config-driven yoga evaluation."""

from .condition_engine import ConditionContext, ConditionEngine
from .models import (
    ChartSnapshot,
    LocalizedPrediction,
    PlanetPlacement,
    StrengthRule,
    YogaCondition,
    YogaDefinition,
    normalize_planet_id,
)

__all__ = [
    "ConditionContext",
    "ConditionEngine",
    "ChartSnapshot",
    "LocalizedPrediction",
    "PlanetPlacement",
    "StrengthRule",
    "YogaCondition",
    "YogaDefinition",
    "YogaEngine",
    "YogaResult",
    "normalize_planet_id",
]


def __getattr__(name: str):
    if name in {"YogaEngine", "YogaResult"}:
        from .yoga_engine import YogaEngine, YogaResult

        return {"YogaEngine": YogaEngine, "YogaResult": YogaResult}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
