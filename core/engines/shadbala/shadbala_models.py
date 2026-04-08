from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass(frozen=True)
class PlanetShadbala:
    """
    Shadbala breakdown for a single planet.
    Values are in Virupas (60 Virupas = 1 Shashtiamsha).
    """
    planet: str
    sthana_bala: float = 0.0    # Positional
    dik_bala: float = 0.0       # Directional
    kala_bala: float = 0.0      # Temporal
    chestha_bala: float = 0.0    # Motional
    naisargika_bala: float = 0.0 # Natural
    drik_bala: float = 0.0       # Aspectual
    is_vargottama: bool = False  # Same sign in D1 and D9
    
    @property
    def total(self) -> float:
        return (self.sthana_bala + self.dik_bala + self.kala_bala + 
                self.chestha_bala + self.naisargika_bala + self.drik_bala)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "planet": self.planet,
            "sthana_bala": round(self.sthana_bala, 2),
            "dik_bala": round(self.dik_bala, 2),
            "kala_bala": round(self.kala_bala, 2),
            "chestha_bala": round(self.chestha_bala, 2),
            "naisargika_bala": round(self.naisargika_bala, 2),
            "drik_bala": round(self.drik_bala, 2),
            "is_vargottama": self.is_vargottama,
            "total": round(self.total, 2)
        }

@dataclass
class ShadbalaResult:
    """Aggregate result for the entire chart."""
    planets: Dict[str, PlanetShadbala] = field(default_factory=dict)
    
    def as_dict(self) -> Dict[str, Any]:
        return {p: s.as_dict() for p, s in self.planets.items()}
