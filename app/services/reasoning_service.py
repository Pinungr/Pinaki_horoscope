from __future__ import annotations

import re
from typing import Any, Dict, Iterable, Mapping


class ReasoningService:
    """
    Builds human-readable reasoning blocks from unified prediction rows.

    Expected prediction row shape:
    {
        "yoga": "Raj Yoga",
        "area": "career",
        "strength": "strong",
        "score": 92,
        "timing": {
            "mahadasha": "Jupiter",
            "antardasha": "Venus",
            "relevance": "high",
            "matched_planets": ["jupiter"]
        }
    }
    """

    AREA_KEYWORDS: Dict[str, tuple[str, ...]] = {
        "career": ("career", "job", "jobs", "work", "profession", "promotion", "office", "business"),
        "marriage": ("marriage", "partner", "relationship", "relationships", "love", "spouse", "wedding"),
        "finance": ("finance", "finances", "financial", "money", "wealth", "income", "salary", "earnings", "cash"),
        "health": ("health", "wellness", "disease", "healing", "fitness"),
        "home": ("home", "family", "house", "property"),
        "education": ("education", "study", "studies", "learning", "exam"),
        "communication": ("communication", "speech", "writing", "media"),
        "self": ("self", "personality", "identity", "confidence"),
        "luck": ("luck", "fortune", "blessing"),
        "gains": ("gains", "network", "social", "income growth"),
        "transformation": ("transformation", "change", "sudden"),
        "general": ("general",),
    }

    AREA_ALIASES: Dict[str, str] = {
        "wealth": "finance",
        "financial": "finance",
        "loss/spiritual": "general",
    }

    def generate_explanations(
        self,
        predictions: Iterable[Mapping[str, Any]],
        user_question: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Generates structured reasoning entries for prediction rows.

        If a user question references one or more areas, rows are filtered to those areas.
        """
        target_areas = self._detect_requested_areas(user_question)
        reasoning_rows: list[dict[str, Any]] = []

        for prediction in predictions or []:
            if not isinstance(prediction, Mapping):
                continue
            area = self._normalize_area(str(prediction.get("area", "general")).strip().lower() or "general")
            if target_areas and area not in target_areas:
                continue
            reasoning_rows.append(self.generate_prediction_reasoning(prediction))

        return reasoning_rows

    def generate_prediction_reasoning(self, prediction: Mapping[str, Any]) -> dict[str, Any]:
        """Explanation generator function for a single prediction row."""
        yoga = str(prediction.get("yoga", "")).strip() or "This yoga"
        raw_area = str(prediction.get("area", "general")).strip().lower() or "general"
        area = self._normalize_area(raw_area)
        area_label = area.replace("_", " ")

        strength = str(prediction.get("strength", "medium")).strip().lower() or "medium"
        score = self._safe_score(prediction.get("score"))
        timing = prediction.get("timing") if isinstance(prediction.get("timing"), Mapping) else {}
        relevance = str(timing.get("relevance", "low")).strip().lower() or "low"
        mahadasha = str(timing.get("mahadasha", "")).strip()
        antardasha = str(timing.get("antardasha", "")).strip()

        explanation_parts = [
            f"Your {area_label} outlook is {self._strength_descriptor(strength)} because {yoga} is present.",
            f"The yoga shows {self._strength_evidence_phrase(strength, score)}.",
        ]
        timing_line = self._timing_explanation_line(relevance, mahadasha, antardasha)
        if timing_line:
            explanation_parts.append(timing_line)

        supporting_factors = self._build_supporting_factors(prediction, strength, score, relevance, mahadasha, antardasha)

        return {
            "area": area,
            "explanation": " ".join(part for part in explanation_parts if part).strip(),
            "supporting_factors": supporting_factors,
        }

    def _build_supporting_factors(
        self,
        prediction: Mapping[str, Any],
        strength: str,
        score: int,
        relevance: str,
        mahadasha: str,
        antardasha: str,
    ) -> list[str]:
        yoga = str(prediction.get("yoga", "")).strip()
        factors: list[str] = []

        if yoga:
            factors.append(f"{yoga} detected")

        strength_label = "Strong" if strength == "strong" else "Moderate" if strength == "medium" else "Mild"
        factors.append(f"{strength_label} strength score ({score})")

        if relevance == "high":
            if mahadasha:
                factors.append(f"{mahadasha} Mahadasha active")
            if antardasha:
                factors.append(f"{antardasha} Antardasha reinforces the result")
        elif relevance == "medium":
            if antardasha:
                factors.append(f"{antardasha} Antardasha provides timing support")
            elif mahadasha:
                factors.append(f"{mahadasha} Mahadasha provides timing support")

        timing = prediction.get("timing")
        matched_planets = []
        if isinstance(timing, Mapping):
            raw = timing.get("matched_planets", [])
            if isinstance(raw, (list, tuple, set)):
                matched_planets = [str(planet).strip().title() for planet in raw if str(planet).strip()]
        if matched_planets:
            factors.append(f"Matched planets: {', '.join(matched_planets)}")

        return factors

    def _detect_requested_areas(self, user_question: str | None) -> set[str]:
        if not str(user_question or "").strip():
            return set()

        tokens = set(re.findall(r"[a-z]+", str(user_question or "").lower()))
        if not tokens:
            return set()

        selected: set[str] = set()
        for area, keywords in self.AREA_KEYWORDS.items():
            if any(keyword in tokens for keyword in keywords):
                selected.add(area)
        return {self._normalize_area(area) for area in selected}

    def _normalize_area(self, area: str) -> str:
        normalized = str(area or "general").strip().lower() or "general"
        return self.AREA_ALIASES.get(normalized, normalized)

    @staticmethod
    def _safe_score(value: Any) -> int:
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _strength_descriptor(strength: str) -> str:
        if strength == "strong":
            return "strong"
        if strength == "weak":
            return "more gradual"
        return "supportive"

    @staticmethod
    def _strength_evidence_phrase(strength: str, score: int) -> str:
        if strength == "strong":
            return f"a high strength profile (score {score})"
        if strength == "weak":
            return f"a modest strength profile (score {score})"
        return f"a balanced strength profile (score {score})"

    @staticmethod
    def _timing_explanation_line(relevance: str, mahadasha: str, antardasha: str) -> str:
        if relevance == "high":
            if mahadasha and antardasha:
                return (
                    f"Timing is especially favorable in {mahadasha} Mahadasha, "
                    f"particularly during {antardasha} Antardasha."
                )
            if mahadasha:
                return f"Timing is especially favorable in {mahadasha} Mahadasha."
            if antardasha:
                return f"Timing is especially favorable in {antardasha} Antardasha."
        if relevance == "medium":
            if antardasha:
                return f"The result is likely to be noticeable in {antardasha} Antardasha."
            if mahadasha:
                return f"The result is likely to be noticeable in {mahadasha} Mahadasha."
        return ""


def generate_prediction_explanation(prediction: Mapping[str, Any]) -> dict[str, Any]:
    """Convenience explanation generator function for one prediction."""
    return ReasoningService().generate_prediction_reasoning(prediction)
