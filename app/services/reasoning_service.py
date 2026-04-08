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
    _SUPPORTED_LANGUAGES = {"en", "hi", "or"}
    _TEMPLATES: Dict[str, Dict[str, str]] = {
        "en": {
            "explain_outlook": "Your {area} outlook is {descriptor} because {yoga} is present.",
            "explain_evidence": "The yoga shows {phrase}.",
            "timing_high_both": "Timing is especially favorable in {maha} Mahadasha, particularly during {antar} Antardasha.",
            "timing_high_maha": "Timing is especially favorable in {maha} Mahadasha.",
            "timing_high_antar": "Timing is especially favorable in {antar} Antardasha.",
            "timing_medium_antar": "The result is likely to be noticeable in {antar} Antardasha.",
            "timing_medium_maha": "The result is likely to be noticeable in {maha} Mahadasha.",
            "factor_detected": "{yoga} detected",
            "factor_strength_score": "{strength_label} strength score ({score})",
            "factor_maha_active": "{maha} Mahadasha active",
            "factor_antar_reinforces": "{antar} Antardasha reinforces the result",
            "factor_antar_support": "{antar} Antardasha provides timing support",
            "factor_maha_support": "{maha} Mahadasha provides timing support",
            "factor_matched_planets": "Matched planets: {planets}",
            "summary_top_focus": "Top focus areas are {labels}.",
            "summary_timing": "Timing is strongest around {labels}.",
            "summary_confidence": "Overall confidence is {confidence}%.",
            "summary_no_data": "No structured insights are available yet.",
            "supporting_factors": "Supporting factors:",
            "descriptor_strong": "strong",
            "descriptor_medium": "supportive",
            "descriptor_weak": "more gradual",
            "evidence_strong": "a high strength profile (score {score})",
            "evidence_medium": "a balanced strength profile (score {score})",
            "evidence_weak": "a modest strength profile (score {score})",
            "strength_label_strong": "Strong",
            "strength_label_medium": "Moderate",
            "strength_label_weak": "Mild",
        },
        "hi": {
            "explain_outlook": "{yoga} की उपस्थिति के कारण आपका {area} परिणाम {descriptor} है।",
            "explain_evidence": "यह योग {phrase} दिखाता है।",
            "timing_high_both": "{maha} महादशा और विशेष रूप से {antar} अंतरदशा में समय अधिक अनुकूल है।",
            "timing_high_maha": "{maha} महादशा में समय अधिक अनुकूल है।",
            "timing_high_antar": "{antar} अंतरदशा में समय अधिक अनुकूल है।",
            "timing_medium_antar": "{antar} अंतरदशा में यह परिणाम अधिक दिख सकता है।",
            "timing_medium_maha": "{maha} महादशा में यह परिणाम अधिक दिख सकता है।",
            "factor_detected": "{yoga} सक्रिय है",
            "factor_strength_score": "{strength_label} शक्ति स्कोर ({score})",
            "factor_maha_active": "{maha} महादशा सक्रिय",
            "factor_antar_reinforces": "{antar} अंतरदशा परिणाम को मजबूत करती है",
            "factor_antar_support": "{antar} अंतरदशा समय-सहयोग देती है",
            "factor_maha_support": "{maha} महादशा समय-सहयोग देती है",
            "factor_matched_planets": "मेल खाते ग्रह: {planets}",
            "summary_top_focus": "मुख्य फोकस क्षेत्र हैं: {labels}।",
            "summary_timing": "समय का प्रमुख फोकस: {labels}।",
            "summary_confidence": "कुल भरोसा स्तर {confidence}% है।",
            "summary_no_data": "अभी संरचित संकेत उपलब्ध नहीं हैं।",
            "supporting_factors": "सहायक कारक:",
            "descriptor_strong": "मजबूत",
            "descriptor_medium": "सहायक",
            "descriptor_weak": "धीमा",
            "evidence_strong": "उच्च शक्ति प्रोफाइल (स्कोर {score})",
            "evidence_medium": "संतुलित शक्ति प्रोफाइल (स्कोर {score})",
            "evidence_weak": "हल्का शक्ति प्रोफाइल (स्कोर {score})",
            "strength_label_strong": "मजबूत",
            "strength_label_medium": "मध्यम",
            "strength_label_weak": "हल्का",
        },
        "or": {
            "explain_outlook": "{yoga} ଉପସ୍ଥିତ ଥିବାରୁ ଆପଣଙ୍କ {area} ପରିଦୃଶ୍ୟ {descriptor} ଅଛି।",
            "explain_evidence": "ଏହି ଯୋଗ {phrase} ଦେଖାଏ।",
            "timing_high_both": "{maha} ମହାଦଶା ଏବଂ ବିଶେଷକରି {antar} ଅନ୍ତରଦଶାରେ ସମୟ ଅଧିକ ଅନୁକୂଳ।",
            "timing_high_maha": "{maha} ମହାଦଶାରେ ସମୟ ଅଧିକ ଅନୁକୂଳ।",
            "timing_high_antar": "{antar} ଅନ୍ତରଦଶାରେ ସମୟ ଅଧିକ ଅନୁକୂଳ।",
            "timing_medium_antar": "{antar} ଅନ୍ତରଦଶାରେ ଏହି ଫଳ ଅଧିକ ସ୍ପଷ୍ଟ ହେବ।",
            "timing_medium_maha": "{maha} ମହାଦଶାରେ ଏହି ଫଳ ଅଧିକ ସ୍ପଷ୍ଟ ହେବ।",
            "factor_detected": "{yoga} ସକ୍ରିୟ",
            "factor_strength_score": "{strength_label} ଶକ୍ତି ସ୍କୋର ({score})",
            "factor_maha_active": "{maha} ମହାଦଶା ସକ୍ରିୟ",
            "factor_antar_reinforces": "{antar} ଅନ୍ତରଦଶା ଫଳକୁ ଶକ୍ତିଶାଳୀ କରେ",
            "factor_antar_support": "{antar} ଅନ୍ତରଦଶା ସମୟ ସମର୍ଥନ ଦେଇଥାଏ",
            "factor_maha_support": "{maha} ମହାଦଶା ସମୟ ସମର୍ଥନ ଦେଇଥାଏ",
            "factor_matched_planets": "ମେଳ ହୋଇଥିବା ଗ୍ରହ: {planets}",
            "summary_top_focus": "ମୁଖ୍ୟ କ୍ଷେତ୍ର: {labels}।",
            "summary_timing": "ସମୟ ଫୋକସ୍: {labels}।",
            "summary_confidence": "ମୋଟ ବିଶ୍ୱାସ ସ୍କୋର {confidence}%।",
            "summary_no_data": "ଏପର୍ଯ୍ୟନ୍ତ ଗଠିତ ସୂଚନା ଉପଲବ୍ଧ ନାହିଁ।",
            "supporting_factors": "ସମର୍ଥନ କାରକ:",
            "descriptor_strong": "ଶକ୍ତିଶାଳୀ",
            "descriptor_medium": "ସହାୟକ",
            "descriptor_weak": "ଧୀର",
            "evidence_strong": "ଉଚ୍ଚ ଶକ୍ତି ପ୍ରୋଫାଇଲ୍ (ସ୍କୋର {score})",
            "evidence_medium": "ସନ୍ତୁଳିତ ଶକ୍ତି ପ୍ରୋଫାଇଲ୍ (ସ୍କୋର {score})",
            "evidence_weak": "ମୃଦୁ ଶକ୍ତି ପ୍ରୋଫାଇଲ୍ (ସ୍କୋର {score})",
            "strength_label_strong": "ଶକ୍ତିଶାଳୀ",
            "strength_label_medium": "ମଧ୍ୟମ",
            "strength_label_weak": "ମୃଦୁ",
        },
    }

    def generate_explanations(
        self,
        predictions: Iterable[Mapping[str, Any]],
        user_question: str | None = None,
        *,
        language: str = "en",
    ) -> list[dict[str, Any]]:
        """
        Generates structured reasoning entries for prediction rows.

        If a user question references one or more areas, rows are filtered to those areas.
        """
        normalized_language = self._normalize_language(language)
        target_areas = self._detect_requested_areas(user_question)
        reasoning_rows: list[dict[str, Any]] = []

        for prediction in predictions or []:
            if not isinstance(prediction, Mapping):
                continue
            area = self._normalize_area(str(prediction.get("area", "general")).strip().lower() or "general")
            if target_areas and area not in target_areas:
                continue
            reasoning_rows.append(self.generate_prediction_reasoning(prediction, language=normalized_language))

        return reasoning_rows

    def generate_prediction_reasoning(self, prediction: Mapping[str, Any], *, language: str = "en") -> dict[str, Any]:
        """Explanation generator function for a single prediction row."""
        normalized_language = self._normalize_language(language)
        templates = self._TEMPLATES[normalized_language]
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
            templates["explain_outlook"].format(
                area=area_label,
                descriptor=self._strength_descriptor(strength, language=normalized_language),
                yoga=yoga,
            ),
            templates["explain_evidence"].format(
                phrase=self._strength_evidence_phrase(strength, score, language=normalized_language)
            ),
        ]
        timing_line = self._timing_explanation_line(
            relevance,
            mahadasha,
            antardasha,
            language=normalized_language,
        )
        if timing_line:
            explanation_parts.append(timing_line)

        supporting_factors = self._build_supporting_factors(
            prediction,
            strength,
            score,
            relevance,
            mahadasha,
            antardasha,
            language=normalized_language,
        )

        return {
            "area": area,
            "explanation": " ".join(part for part in explanation_parts if part).strip(),
            "supporting_factors": supporting_factors,
        }

    def build_ui_payload(
        self,
        predictions: Iterable[Mapping[str, Any]],
        *,
        summary: Mapping[str, Any] | None = None,
        user_question: str | None = None,
        language: str = "en",
    ) -> dict[str, Any]:
        """
        Builds a compact pre-UI contract for cards/lists.

        Output shape:
        {
            "summary": "...",
            "details": [
                {
                    "rule": "gajakesari_yoga",
                    "text": "...",
                    "explanation": "...",
                    "weight": 9
                }
            ]
        }
        """
        normalized_language = self._normalize_language(language)
        target_areas = self._detect_requested_areas(user_question)
        detail_rows: list[dict[str, Any]] = []

        for prediction in predictions or []:
            if not isinstance(prediction, Mapping):
                continue

            area = self._normalize_area(str(prediction.get("area", "general")).strip().lower() or "general")
            if target_areas and area not in target_areas:
                continue

            reasoning = self.generate_prediction_reasoning(prediction, language=normalized_language)
            text = str(prediction.get("refined_text") or prediction.get("text") or "").strip()
            if not text:
                text = str(reasoning.get("explanation", "")).strip()

            detail_rows.append(
                {
                    "rule": self._build_rule_key(prediction),
                    "text": text,
                    "explanation": str(reasoning.get("explanation", "")).strip(),
                    "weight": self._build_ui_weight(prediction),
                }
            )

        return {
            "summary": self._build_ui_summary(summary, detail_rows, language=normalized_language),
            "details": detail_rows,
        }

    def _build_supporting_factors(
        self,
        prediction: Mapping[str, Any],
        strength: str,
        score: int,
        relevance: str,
        mahadasha: str,
        antardasha: str,
        *,
        language: str,
    ) -> list[str]:
        templates = self._TEMPLATES[language]
        yoga = str(prediction.get("yoga", "")).strip()
        factors: list[str] = []

        if yoga:
            factors.append(templates["factor_detected"].format(yoga=yoga))

        if strength == "strong":
            strength_label = templates["strength_label_strong"]
        elif strength == "medium":
            strength_label = templates["strength_label_medium"]
        else:
            strength_label = templates["strength_label_weak"]
        factors.append(templates["factor_strength_score"].format(strength_label=strength_label, score=score))

        if relevance == "high":
            if mahadasha:
                factors.append(templates["factor_maha_active"].format(maha=mahadasha))
            if antardasha:
                factors.append(templates["factor_antar_reinforces"].format(antar=antardasha))
        elif relevance == "medium":
            if antardasha:
                factors.append(templates["factor_antar_support"].format(antar=antardasha))
            elif mahadasha:
                factors.append(templates["factor_maha_support"].format(maha=mahadasha))

        timing = prediction.get("timing")
        matched_planets = []
        if isinstance(timing, Mapping):
            raw = timing.get("matched_planets", [])
            if isinstance(raw, (list, tuple, set)):
                matched_planets = [str(planet).strip().title() for planet in raw if str(planet).strip()]
        if matched_planets:
            factors.append(templates["factor_matched_planets"].format(planets=", ".join(matched_planets)))

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

    def _strength_evidence_phrase(self, strength: str, score: int, *, language: str) -> str:
        templates = self._TEMPLATES[language]
        if strength == "strong":
            return templates["evidence_strong"].format(score=score)
        if strength == "weak":
            return templates["evidence_weak"].format(score=score)
        return templates["evidence_medium"].format(score=score)

    def _timing_explanation_line(
        self,
        relevance: str,
        mahadasha: str,
        antardasha: str,
        *,
        language: str,
    ) -> str:
        templates = self._TEMPLATES[language]
        if relevance == "high":
            if mahadasha and antardasha:
                return templates["timing_high_both"].format(maha=mahadasha, antar=antardasha)
            if mahadasha:
                return templates["timing_high_maha"].format(maha=mahadasha)
            if antardasha:
                return templates["timing_high_antar"].format(antar=antardasha)
        if relevance == "medium":
            if antardasha:
                return templates["timing_medium_antar"].format(antar=antardasha)
            if mahadasha:
                return templates["timing_medium_maha"].format(maha=mahadasha)
        return ""

    @staticmethod
    def _build_rule_key(prediction: Mapping[str, Any]) -> str:
        explicit_rule = str(prediction.get("rule") or prediction.get("id") or "").strip().lower()
        if explicit_rule:
            return explicit_rule

        yoga = str(prediction.get("yoga", "")).strip().lower()
        slug = re.sub(r"[^a-z0-9]+", "_", yoga).strip("_")
        return slug or "general_prediction"

    def _build_ui_summary(
        self,
        summary: Mapping[str, Any] | None,
        detail_rows: list[dict[str, Any]],
        *,
        language: str,
    ) -> str:
        templates = self._TEMPLATES[language]
        if isinstance(summary, Mapping):
            top_areas = summary.get("top_areas", [])
            if not isinstance(top_areas, list):
                top_areas = []
            normalized_areas = [
                self._normalize_area(str(area).strip().lower())
                for area in top_areas
                if str(area or "").strip()
            ]
            time_focus = summary.get("time_focus", [])
            if not isinstance(time_focus, list):
                time_focus = []
            normalized_time_focus = [
                self._normalize_area(str(area).strip().lower())
                for area in time_focus
                if str(area or "").strip()
            ]
            confidence = self._safe_score(summary.get("confidence_score"))

            parts: list[str] = []
            if normalized_areas:
                labels = ", ".join(area.replace("_", " ") for area in normalized_areas[:3])
                parts.append(templates["summary_top_focus"].format(labels=labels))
            if normalized_time_focus:
                labels = ", ".join(area.replace("_", " ") for area in normalized_time_focus[:3])
                parts.append(templates["summary_timing"].format(labels=labels))
            if confidence > 0:
                parts.append(templates["summary_confidence"].format(confidence=confidence))
            if parts:
                return " ".join(parts)

        if detail_rows:
            return str(detail_rows[0].get("text", "")).strip()

        return templates["summary_no_data"]

    def _build_ui_weight(self, prediction: Mapping[str, Any]) -> int:
        explicit_weight = prediction.get("weight")
        if explicit_weight is not None:
            return max(0, self._safe_score(explicit_weight))

        score = self._safe_score(prediction.get("score"))
        if score <= 0:
            return 0
        return max(1, min(10, int(round(score / 10.0))))

    def _strength_descriptor(self, strength: str, *, language: str) -> str:
        templates = self._TEMPLATES[language]
        if strength == "strong":
            return templates["descriptor_strong"]
        if strength == "weak":
            return templates["descriptor_weak"]
        return templates["descriptor_medium"]

    def _normalize_language(self, language: str) -> str:
        normalized = str(language or "en").strip().lower() or "en"
        if normalized not in self._SUPPORTED_LANGUAGES:
            return "en"
        return normalized


def generate_prediction_explanation(prediction: Mapping[str, Any]) -> dict[str, Any]:
    """Convenience explanation generator function for one prediction."""
    return ReasoningService().generate_prediction_reasoning(prediction)
