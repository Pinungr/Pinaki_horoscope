from dataclasses import dataclass
from typing import Optional

@dataclass
class User:
    name: str
    dob: str
    tob: str
    place: str
    latitude: float
    longitude: float
    state: Optional[str] = None
    city: Optional[str] = None
    id: Optional[int] = None

@dataclass
class Planet:
    name: str
    id: Optional[int] = None

@dataclass
class ChartData:
    user_id: int
    planet_name: str
    sign: str
    house: int
    degree: float
    id: Optional[int] = None

@dataclass
class Rule:
    condition_json: str
    result_text: str
    result_key: Optional[str] = None
    priority: int = 0
    category: Optional[str] = None
    effect: str = "positive"
    weight: float = 1.0
    confidence: str = "medium"
    id: Optional[int] = None

    def __post_init__(self) -> None:
        """Normalizes optional scoring fields while remaining backward compatible."""
        self.result_key = str(self.result_key or "").strip() or None
        self.category = self.category or "general"
        self.effect = (self.effect or "positive").strip().lower()
        if self.effect not in {"positive", "negative"}:
            self.effect = "positive"

        self.weight = abs(float(self.weight or 1.0))

        normalized_confidence = (self.confidence or "medium").strip().lower()
        if normalized_confidence not in {"low", "medium", "high"}:
            normalized_confidence = "medium"
        self.confidence = normalized_confidence
