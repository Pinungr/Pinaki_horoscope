from dataclasses import dataclass
from typing import Optional, List

@dataclass
class User:
    name: str
    dob: str
    tob: str
    place: str
    latitude: float
    longitude: float
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
    priority: int = 0
    category: Optional[str] = None
    id: Optional[int] = None
