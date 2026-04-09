from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Mapping

from app.engine.dasha import DashaEngine
from app.engine.varga_engine import VargaEngine
from core.engines.dignity_engine import DignityEngine
from core.utils.chart_utils import get_planet_house, normalize_planet_name

from app.utils.runtime_paths import resolve_resource


class PredictionService:
    """Loads localized prediction meanings from a key-based JSON registry."""

    DEFAULT_LANGUAGE = "en"
    HOUSE_AREA_MAP: Dict[int, str] = {
        1: "self",
        2: "wealth",
        3: "communication",
        4: "home",
        5: "education",
        6: "health",
        7: "marriage",
        8: "transformation",
        9: "luck",
        10: "career",
        11: "gains",
        12: "loss/spiritual",
    }
    KNOWN_PLANETS = {
        "sun",
        "moon",
        "mars",
        "mercury",
        "jupiter",
        "venus",
        "saturn",
        "rahu",
        "ketu",
    }
    SUPPORTED_LANGUAGES = {"en", "hi", "or"}
    BHAVA_AREA_FRAMEWORK: Dict[str, Dict[str, Any]] = {
        "career": {
            "houses": [10],
            "label": "Career",
        },
        "marriage": {
            "houses": [7],
            "label": "Marriage",
        },
        "finance": {
            "houses": [2, 11],
            "label": "Finance",
        },
        "health": {
            "houses": [6],
            "label": "Health",
        },
    }
    DEFAULT_KARAKA_REGISTRY: Dict[str, list[str]] = {
        "career": ["saturn", "sun", "mercury"],
        "marriage": ["venus", "jupiter"],
        "finance": ["jupiter", "venus"],
        "health": ["sun", "moon", "mars"],
    }
    AREA_REGISTRY_ALIASES: Dict[str, str] = {
        "profession": "career",
        "wealth": "finance",
        "gains": "finance",
        "income": "finance",
        "money": "finance",
        "relationship": "marriage",
        "relationships": "marriage",
    }
    _PLANET_STRENGTH_TARGETS: Dict[str, float] = {
        "sun": 390.0,
        "moon": 360.0,
        "mars": 300.0,
        "mercury": 420.0,
        "jupiter": 390.0,
        "venus": 330.0,
        "saturn": 300.0,
    }
    _STRONG_DIGNITIES = {"exalted", "own", "friendly"}
    _WEAK_DIGNITIES = {"debilitated", "enemy"}
    _DIGNITY_SCORE = {
        "exalted": 1.4,
        "own": 1.1,
        "friendly": 0.7,
        "neutral": 0.0,
        "enemy": -0.8,
        "debilitated": -1.2,
    }
    _ACTIVATION_LEVEL_ORDER = {"low": 0, "medium": 1, "high": 2}
    _ACTIVATION_FLOOR_SCORE = {"low": 0.0, "medium": 40.0, "high": 67.0}
    _KARAKA_MODIFIER_MIN = 0.5
    _KARAKA_MODIFIER_MAX = 1.2
    _KARAKA_CONTRIBUTION_BASE = {
        "supportive": 1.12,
        "neutral": 1.0,
        "adverse": 0.72,
    }
    FINAL_LAYER_WEIGHTS = {
        "strength": 0.35,
        "functional_nature": 0.15,
        "lordship": 0.2,
        "yoga": 0.3,
    }
    CONFLICT_RESOLUTION_PRIORITY = [
        "strength_gate",
        "dasha_activation",
        "house_lord_condition",
        "yoga_status",
        "varga_concordance",
        "transit_trigger",
    ]
    CONFLICT_RESOLUTION_THRESHOLDS = {
        "strength_min_score": 52.0,
        "strength_strong_score": 68.0,
        "dasha_active_multiplier_min": 0.98,
        "lordship_strong_score": 65.0,
        "lordship_weak_score": 40.0,
        "lordship_weak_multiplier": 0.7,
        "varga_conflict_score_max": 0.4,
        "varga_conflict_confidence_multiplier": 0.72,
        "varga_conflict_score_multiplier": 0.92,
    }

    def __init__(
        self,
        meanings_path: Path | None = None,
        *,
        final_layer_weights: Mapping[str, Any] | None = None,
        karaka_registry: Mapping[str, Any] | None = None,
    ) -> None:
        self.meanings_path = meanings_path or resolve_resource("core", "predictions", "meanings.json")
        self._meanings: Dict[str, Dict[str, Any]] | None = None
        self._dasha_engine = DashaEngine()
        self._varga_engine = VargaEngine()
        self._final_layer_weights = self._normalize_final_layer_weights(final_layer_weights)
        self._karaka_registry = self._normalize_karaka_registry(karaka_registry)

    def get_final_layer_weights(self) -> Dict[str, float]:
        """
        Returns deterministic M8 layer weights.
        """
        return dict(self._final_layer_weights)

    def get_conflict_resolution_priority(self) -> list[str]:
        """
        Returns deterministic M9 conflict resolution priority.
        """
        return list(self.CONFLICT_RESOLUTION_PRIORITY)

    def get_conflict_resolution_thresholds(self) -> Dict[str, float]:
        """
        Returns deterministic M9 conflict resolution thresholds.
        """
        return dict(self.CONFLICT_RESOLUTION_THRESHOLDS)

    def normalize_area_key(self, area: Any) -> str:
        normalized_area = str(area or "").strip().lower()
        if not normalized_area:
            return ""
        return self.AREA_REGISTRY_ALIASES.get(normalized_area, normalized_area)

    def get_karakas(self, area: Any) -> list[str]:
        normalized_area = self.normalize_area_key(area)
        if not normalized_area:
            return []

        configured = self._karaka_registry.get(normalized_area)
        if isinstance(configured, list):
            return list(configured)

        fallback_framework = self.BHAVA_AREA_FRAMEWORK.get(normalized_area, {})
        if isinstance(fallback_framework, Mapping):
            return self._normalize_planet_list(fallback_framework.get("karakas", []))
        return []

    def get_prediction(self, rule_key: Any, language: str | None = None) -> str:
        normalized_key = str(rule_key or "").strip()
        if not normalized_key:
            return ""

        normalized_language = str(language or self.DEFAULT_LANGUAGE).strip().lower() or self.DEFAULT_LANGUAGE
        meanings = self._load_meanings()
        meaning_entry = meanings.get(normalized_key, {})
        if not isinstance(meaning_entry, dict):
            return ""

        localized_text = meaning_entry.get(normalized_language)
        if localized_text:
            return str(localized_text).strip()

        fallback_text = meaning_entry.get(self.DEFAULT_LANGUAGE)
        if fallback_text:
            return str(fallback_text).strip()

        return ""

    def get_weight(self, rule_key: Any) -> float:
        normalized_key = str(rule_key or "").strip()
        if not normalized_key:
            return 0.0

        meaning_entry = self._load_meanings().get(normalized_key, {})
        if not isinstance(meaning_entry, dict):
            return 0.0

        raw_weight = meaning_entry.get("weight", 0.0)
        try:
            return float(raw_weight or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def map_yoga_to_planets(self, yoga: Any) -> list[str]:
        """
        Extracts involved planets for one yoga definition/result in normalized form.

        Returns lowercase planet ids (e.g. ["moon", "jupiter"]).
        """
        extracted: list[str] = []
        seen: set[str] = set()

        def _add(raw_planet: Any) -> None:
            normalized = normalize_planet_name(raw_planet)
            if normalized and normalized in self.KNOWN_PLANETS and normalized not in seen:
                seen.add(normalized)
                extracted.append(normalized)

        for key in ("key_planets", "planets"):
            raw_values = self._read_value(yoga, key, [])
            if isinstance(raw_values, (list, tuple, set)):
                for item in raw_values:
                    _add(item)

        for key in ("planet", "from", "to", "from_planet", "to_planet"):
            _add(self._read_value(yoga, key))

        if not extracted:
            yoga_id = str(self._read_value(yoga, "id", self._read_value(yoga, "yoga", "")) or "").lower()
            for planet in self.KNOWN_PLANETS:
                if planet in yoga_id and planet not in seen:
                    seen.add(planet)
                    extracted.append(planet)

        return extracted

    def evaluate_dasha_relevance(
        self,
        yoga: Any,
        dasha_data: Any,
        *,
        reference_date: date | None = None,
        chart_data: Any = None,
        prediction_context: Mapping[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """
        Computes dasha relevance for one yoga.

        Output shape:
        {
            "mahadasha": "Jupiter",
            "antardasha": "Venus",
            "relevance": "high" | "medium" | "low",
            "matched_planets": [...],
            "score_multiplier": float
        }
        """
        yoga_planets = self.map_yoga_to_planets(yoga)
        dasha_context = self.get_current_dasha_context(dasha_data, reference_date=reference_date)

        mahadasha_lord = normalize_planet_name(dasha_context.get("mahadasha"))
        antardasha_lord = normalize_planet_name(dasha_context.get("antardasha"))
        matched_planets: list[str] = []

        maha_match = mahadasha_lord in yoga_planets if mahadasha_lord else False
        antar_match = antardasha_lord in yoga_planets if antardasha_lord else False
        if maha_match and mahadasha_lord:
            matched_planets.append(mahadasha_lord)
        if antar_match and antardasha_lord and antardasha_lord not in matched_planets:
            matched_planets.append(antardasha_lord)

        if maha_match and antar_match:
            legacy_relevance = "high"
        elif maha_match:
            legacy_relevance = "high"
        elif antar_match:
            legacy_relevance = "medium"
        else:
            legacy_relevance = "low"

        activation_context = self._build_dasha_activation_context(
            yoga=yoga,
            chart_data=chart_data,
            prediction_context=prediction_context,
            yoga_planets=yoga_planets,
        )
        activation = self.get_dasha_activation(
            chart_data,
            {
                "mahadasha": dasha_context.get("mahadasha"),
                "antardasha": dasha_context.get("antardasha"),
            },
            activation_context,
        )

        activation_score = self._coerce_float(activation.get("activation_score"), 0.0)
        activation_level = str(activation.get("activation_level", "low")).strip().lower() or "low"
        allow_legacy_promotion = chart_data is None and prediction_context is None
        relevance = (
            self._resolve_highest_activation_level(activation_level, legacy_relevance)
            if allow_legacy_promotion
            else activation_level
        )
        if allow_legacy_promotion and relevance != activation_level:
            activation_score = max(activation_score, self._ACTIVATION_FLOOR_SCORE.get(relevance, 0.0))

        dasha_evidence = self._extract_dasha_evidence(activation.get("contributing_factors"))
        if not dasha_evidence:
            if maha_match and mahadasha_lord:
                dasha_evidence.append(
                    f"Current Mahadasha lord {mahadasha_lord.capitalize()} directly supports this promise."
                )
            elif antar_match and antardasha_lord:
                dasha_evidence.append(
                    f"Current Antardasha lord {antardasha_lord.capitalize()} directly supports this promise."
                )
            else:
                dasha_evidence.append("Current dasha context has limited activation overlap with this promise.")

        activation_matches = activation.get("matched_planets", [])
        if isinstance(activation_matches, (list, tuple, set)):
            for planet in activation_matches:
                normalized = normalize_planet_name(planet)
                if normalized and normalized not in matched_planets:
                    matched_planets.append(normalized)

        d10_validation = {
            "status": "neutral",
            "factors": ["D10 validation not applied for this prediction area."],
            "multiplier": 1.0,
            "score": 0.0,
        }
        prediction_area = str(activation_context.get("area", "general")).strip().lower() or "general"
        if prediction_area == "career":
            d10_validation = self.evaluate_d10_career_validation(
                chart_data=chart_data,
                prediction_context=activation_context,
            )
            d10_factors = d10_validation.get("factors", [])
            if isinstance(d10_factors, (list, tuple)):
                for factor in d10_factors:
                    text = str(factor or "").strip()
                    if text and text not in dasha_evidence:
                        dasha_evidence.append(text)

        if not mahadasha_lord and not antardasha_lord:
            activation_multiplier = 1.0
        else:
            activation_multiplier = self._compute_activation_multiplier(activation_score, relevance)
        d10_multiplier = self._coerce_float(d10_validation.get("multiplier"), 1.0)
        multiplier = round(max(0.72, min(1.35, activation_multiplier * d10_multiplier)), 3)

        return {
            "mahadasha": dasha_context.get("mahadasha"),
            "antardasha": dasha_context.get("antardasha"),
            "relevance": relevance,
            "activation_level": relevance,
            "activation_score": round(activation_score, 2),
            "matched_planets": matched_planets,
            "score_multiplier": multiplier,
            "dasha_multiplier": round(activation_multiplier, 3),
            "d10_multiplier": round(d10_multiplier, 3),
            "d10_status": str(d10_validation.get("status", "neutral")).strip().lower() or "neutral",
            "d10_evidence": list(d10_validation.get("factors", []) or []),
            "dasha_evidence": dasha_evidence,
            "contributing_factors": activation.get("contributing_factors", []),
        }

    def build_timing_text(self, timing: Any, language: str | None = None) -> str:
        normalized_language = self._normalize_language(language)
        if not isinstance(timing, dict):
            return ""

        mahadasha = str(timing.get("mahadasha") or "").strip()
        antardasha = str(timing.get("antardasha") or "").strip()
        relevance = str(timing.get("activation_level", timing.get("relevance", "low")) or "low").strip().lower() or "low"

        if not mahadasha and not antardasha:
            return ""

        if relevance == "high":
            if mahadasha and antardasha:
                if normalized_language == "hi":
                    return f"यह प्रभाव {mahadasha} महादशा में, विशेष रूप से {antardasha} अंतरदशा में सबसे मजबूत रहेगा।"
                if normalized_language == "or":
                    return f"ଏହି ପ୍ରଭାବ {mahadasha} ମହାଦଶାରେ, ବିଶେଷକରି {antardasha} ଅନ୍ତରଦଶାରେ ସବୁଠୁ ଶକ୍ତିଶାଳୀ ରହିବ।"
                return (
                    f"This effect is strongest during {mahadasha} Mahadasha, "
                    f"especially in {antardasha} Antardasha."
                )
            if mahadasha:
                if normalized_language == "hi":
                    return f"यह प्रभाव {mahadasha} महादशा में अधिक मजबूत रहेगा।"
                if normalized_language == "or":
                    return f"ଏହି ପ୍ରଭାବ {mahadasha} ମହାଦଶାରେ ଅଧିକ ଶକ୍ତିଶାଳୀ ରହିବ।"
                return f"This effect is stronger during {mahadasha} Mahadasha."
            if normalized_language == "hi":
                return f"यह प्रभाव {antardasha} अंतरदशा में विशेष रूप से सक्रिय रहेगा।"
            if normalized_language == "or":
                return f"ଏହି ପ୍ରଭାବ {antardasha} ଅନ୍ତରଦଶାରେ ବିଶେଷ ଭାବେ ସକ୍ରିୟ ରହିବ।"
            return f"This effect is especially active during {antardasha} Antardasha."

        if relevance == "medium":
            if antardasha:
                if normalized_language == "hi":
                    return f"यह प्रभाव {antardasha} अंतरदशा में बढ़ सकता है।"
                if normalized_language == "or":
                    return f"ଏହି ପ୍ରଭାବ {antardasha} ଅନ୍ତରଦଶାରେ ବଢ଼ି ପାରେ।"
                return f"This effect may rise during {antardasha} Antardasha."
            if mahadasha:
                if normalized_language == "hi":
                    return f"यह प्रभाव {mahadasha} महादशा में बढ़ सकता है।"
                if normalized_language == "or":
                    return f"ଏହି ପ୍ରଭାବ {mahadasha} ମହାଦଶାରେ ବଢ଼ି ପାରେ।"
                return f"This effect may rise during {mahadasha} Mahadasha."
            return ""

        if mahadasha:
            if normalized_language == "hi":
                return f"अभी समय समर्थन सीमित है, {mahadasha} महादशा में हल्का प्रभाव रहेगा।"
            if normalized_language == "or":
                return f"ବର୍ତ୍ତମାନ ସମୟ ସମର୍ଥନ ସୀମିତ, {mahadasha} ମହାଦଶାରେ ହାଲୁକା ପ୍ରଭାବ ରହିବ।"
            return f"Timing support is presently limited, with a milder influence in {mahadasha} Mahadasha."
        if normalized_language == "hi":
            return f"अभी समय समर्थन सीमित है, {antardasha} अंतरदशा में हल्का प्रभाव रहेगा।"
        if normalized_language == "or":
            return f"ବର୍ତ୍ତମାନ ସମୟ ସମର୍ଥନ ସୀମିତ, {antardasha} ଅନ୍ତରଦଶାରେ ହାଲୁକା ପ୍ରଭାବ ରହିବ।"
        return f"Timing support is presently limited, with a milder influence in {antardasha} Antardasha."

    def evaluate_transit_trigger(
        self,
        yoga: Any,
        transit_data: Any,
        *,
        dasha_relevance: Mapping[str, Any] | None = None,
        prediction_context: Mapping[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """
        Transit acts strictly as a timing/intensity modifier for an existing promise.
        It never produces a standalone prediction row.
        """
        context: Dict[str, Any] = dict(prediction_context or {})
        yoga_planets = self._normalize_planet_list(context.get("yoga_planets", self.map_yoga_to_planets(yoga)))
        relevant_houses = [
            h
            for h in (context.get("relevant_houses") or [])
            if self._coerce_house(h) is not None
        ]
        if not relevant_houses:
            house = self._coerce_house(
                context.get(
                    "house",
                    self._read_value(
                        yoga,
                        "house",
                        self._read_value(yoga, "to_house", self._read_value(yoga, "from_house")),
                    ),
                )
            )
            if house is not None:
                relevant_houses = [house]

        area = str(context.get("area", self._read_value(yoga, "area", "")) or "").strip().lower() or "general"
        karakas = self._normalize_planet_list(context.get("karakas"))
        if not karakas:
            karakas = self.get_karakas(area)

        house_lord = self._resolve_primary_house_lord(relevant_houses, context.get("house_lord"), context.get("house_lord_details"))
        dasha_lords = self._normalize_planet_list(
            [
                self._read_value(dasha_relevance, "mahadasha") if isinstance(dasha_relevance, Mapping) else None,
                self._read_value(dasha_relevance, "antardasha") if isinstance(dasha_relevance, Mapping) else None,
            ]
        )

        transit_matrix = self._extract_transit_matrix(transit_data)
        if not transit_matrix:
            return {
                "score_multiplier": 0.95,
                "trigger_level": "low",
                "trigger_now": False,
                "support_state": "neutral",
                "matched_planets": [],
                "source_factors": ["Transit data is unavailable, so no active transit trigger is applied."],
                "dominant_trigger": None,
            }

        positive_score = 0.0
        suppress_score = 0.0
        matched_planets: list[str] = []
        source_factors: list[str] = []
        dominant_trigger: Dict[str, Any] | None = None
        promise_actors = set(yoga_planets + karakas + ([house_lord] if house_lord else []))
        actor_houses = self._resolve_actor_houses(context.get("house_lord_details"), promise_actors)

        for transit_planet, row in transit_matrix.items():
            planet = normalize_planet_name(transit_planet)
            if not planet:
                continue

            from_lagna = row.get("from_lagna", {}) if isinstance(row.get("from_lagna"), Mapping) else {}
            from_moon = row.get("from_moon", {}) if isinstance(row.get("from_moon"), Mapping) else {}
            lagna_house = self._coerce_house(from_lagna.get("house_position", from_lagna.get("house_from_reference")))
            moon_house = self._coerce_house(from_moon.get("house_position", from_moon.get("house_from_reference")))

            hit_lagna = lagna_house in relevant_houses if lagna_house is not None else False
            hit_moon = moon_house in relevant_houses if moon_house is not None else False
            is_actor = planet in promise_actors
            is_dasha_match = planet in dasha_lords

            contribution = 0.0
            if hit_lagna:
                contribution += 0.18 if is_actor else 0.11
            if hit_moon:
                contribution += 0.14 if is_actor else 0.09
            if planet in yoga_planets:
                contribution += 0.1
            if planet in karakas:
                contribution += 0.08
            if house_lord and planet == house_lord:
                contribution += 0.12
            if is_dasha_match:
                contribution += 0.12
            if is_dasha_match and is_actor:
                contribution += 0.07

            contact_reasons: list[str] = []
            max_contact_bonus = 0.0
            if lagna_house is not None and actor_houses:
                for actor_planet, actor_house in actor_houses.items():
                    contact = self._house_contact_label(lagna_house, actor_house)
                    if not contact:
                        continue
                    bonus = 0.1 if contact == "conjunction" else 0.06
                    if bonus > max_contact_bonus:
                        max_contact_bonus = bonus
                    contact_reasons.append(
                        f"{contact} {actor_planet.capitalize()} (natal house {actor_house})"
                    )
            contribution += max_contact_bonus

            hard_lagna = lagna_house in {6, 8, 12} if lagna_house is not None else False
            hard_moon = moon_house in {6, 8, 12} if moon_house is not None else False
            suppression = 0.0
            hard_count = int(hard_lagna) + int(hard_moon)
            if is_actor and hard_count:
                suppression += 0.24 + (0.1 * hard_count)
            if is_dasha_match and hard_count:
                suppression += 0.16 + (0.06 * hard_count)

            if contribution > 0:
                positive_score += contribution
                if planet not in matched_planets:
                    matched_planets.append(planet)
                reason_bits: list[str] = []
                if hit_lagna:
                    reason_bits.append(f"over house {lagna_house} from Lagna")
                if hit_moon:
                    reason_bits.append(f"over house {moon_house} from Moon")
                if is_dasha_match:
                    reason_bits.append("matching current dasha lord")
                if planet in yoga_planets:
                    reason_bits.append("activating yoga planet")
                if planet in karakas:
                    reason_bits.append("supporting area karaka")
                if house_lord and planet == house_lord:
                    reason_bits.append("activating house lord")
                if contact_reasons:
                    reason_bits.append("; ".join(contact_reasons))
                reason = ", ".join(reason_bits) if reason_bits else "reinforcing existing promise"
                source_factors.append(f"Transit of {planet.capitalize()} is {reason}.")

                if dominant_trigger is None or contribution > float(dominant_trigger.get("strength", 0.0)):
                    dominant_trigger = {
                        "planet": planet,
                        "house": lagna_house if lagna_house is not None else moon_house,
                        "reference": "lagna" if hit_lagna else "moon",
                        "strength": round(contribution, 3),
                    }

            if suppression > 0:
                suppress_score += suppression
                source_factors.append(
                    f"Transit of {planet.capitalize()} through challenging houses is suppressing immediate manifestation."
                )

        net = positive_score - suppress_score
        if positive_score == 0.0 and suppress_score == 0.0:
            score_multiplier = 0.95
            trigger_level = "low"
            trigger_now = False
            support_state = "neutral"
            source_factors.append("Current transits are not directly triggering this natal promise.")
        else:
            raw_multiplier = 1.0 + net
            score_multiplier = max(0.72, min(1.3, raw_multiplier))
            if score_multiplier >= 1.15:
                trigger_level = "high"
            elif score_multiplier >= 0.95:
                trigger_level = "medium"
            else:
                trigger_level = "low"
            trigger_now = bool(trigger_level == "high" and positive_score > suppress_score)
            support_state = "amplifying" if score_multiplier > 1.02 else "suppressing" if score_multiplier < 0.98 else "neutral"

        deduped_factors = []
        seen = set()
        for line in source_factors:
            text = str(line or "").strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped_factors.append(text)

        return {
            "score_multiplier": round(score_multiplier, 3),
            "trigger_level": trigger_level,
            "trigger_now": trigger_now,
            "support_state": support_state,
            "matched_planets": matched_planets,
            "source_factors": deduped_factors[:10],
            "dominant_trigger": dominant_trigger,
        }

    def build_transit_trigger_text(self, transit_trigger: Any, *, area: str, timing: Mapping[str, Any] | None = None) -> str:
        if not isinstance(transit_trigger, Mapping):
            return ""

        support_state = str(transit_trigger.get("support_state", "neutral")).strip().lower() or "neutral"
        if support_state == "neutral":
            return ""

        trigger = transit_trigger.get("dominant_trigger", {})
        if not isinstance(trigger, Mapping):
            return ""
        planet = str(trigger.get("planet", "")).strip()
        house = self._coerce_house(trigger.get("house"))
        if not planet or house is None:
            return ""

        mahadasha = str(self._read_value(timing, "mahadasha", "") if isinstance(timing, Mapping) else "").strip()
        dasha_text = f" during {mahadasha} Mahadasha" if mahadasha else ""
        area_label = str(area or "general").strip().lower() or "general"
        if support_state == "amplifying":
            return (
                f"Transit of {planet.capitalize()} over {house}th house is amplifying "
                f"{area_label} promise{dasha_text}."
            )
        return (
            f"Transit of {planet.capitalize()} around {house}th house is currently suppressing "
            f"{area_label} promise{dasha_text}."
        )

    def evaluate_d10_career_validation(
        self,
        *,
        chart_data: Any,
        prediction_context: Mapping[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """
        D10 validates D1 career promise; it never creates a standalone promise.
        """
        context = dict(prediction_context or {})
        d10_input_rows = self._coerce_chart_rows_for_varga(chart_data)
        d10_chart = self._varga_engine.get_d10_chart(d10_input_rows)
        d10_rows = d10_chart.get("rows", []) if isinstance(d10_chart, dict) else []
        if not isinstance(d10_rows, list) or not d10_rows:
            return {
                "status": "neutral",
                "factors": ["D10 chart data is unavailable, so career validation stays neutral."],
                "multiplier": 1.0,
                "score": 0.0,
            }

        d10_lagna = str(d10_chart.get("ascendant_sign", "")).strip().lower()
        if not d10_lagna:
            return {
                "status": "neutral",
                "factors": ["D10 ascendant is unavailable, so career validation stays neutral."],
                "multiplier": 1.0,
                "score": 0.0,
            }

        d10_house_lords = self.get_house_lord_details(d10_rows, lagna_sign=d10_lagna)
        d10_10th = d10_house_lords.get(10, {}) if isinstance(d10_house_lords, dict) else {}
        d10_10th_lord = normalize_planet_name(d10_10th.get("lord"))

        d1_house_lords = context.get("house_lord_details", {})
        if not isinstance(d1_house_lords, Mapping):
            d1_house_lords = self.get_house_lord_details(chart_data)
        d1_10th = d1_house_lords.get(10, {}) if isinstance(d1_house_lords, Mapping) else {}
        d1_10th_lord = normalize_planet_name(
            context.get("d1_tenth_lord")
            or (d1_10th.get("lord") if isinstance(d1_10th, Mapping) else None)
        )

        placements = d10_chart.get("placements", {}) if isinstance(d10_chart, dict) else {}
        score = 0.0
        factors: list[str] = []
        measured_signals = 0

        tenth_eval = self._evaluate_d10_planet_condition(d10_10th_lord, placements, d10_house_lords)
        if d10_10th_lord:
            measured_signals += 1
            if tenth_eval["quality"] == "strong":
                score += 0.95
                factors.append(f"D10 10th lord {d10_10th_lord.capitalize()} is well placed.")
            elif tenth_eval["quality"] == "weak":
                score -= 0.95
                factors.append(f"D10 10th lord {d10_10th_lord.capitalize()} is weakly placed.")
            else:
                factors.append(f"D10 10th lord {d10_10th_lord.capitalize()} gives mixed support.")
        else:
            factors.append("D10 10th lord could not be resolved.")

        d1_eval = self._evaluate_d10_planet_condition(d1_10th_lord, placements, d10_house_lords)
        if d1_10th_lord:
            measured_signals += 1
            if d1_eval["quality"] == "strong":
                score += 0.75
                factors.append(f"D1 10th lord {d1_10th_lord.capitalize()} is supportive in D10.")
            elif d1_eval["quality"] == "weak":
                score -= 0.85
                factors.append(f"D1 10th lord {d1_10th_lord.capitalize()} is stressed in D10.")
            else:
                factors.append(f"D1 10th lord {d1_10th_lord.capitalize()} is neutral in D10.")
        else:
            factors.append("D1 10th lord is unavailable for D10 cross-validation.")

        for karaka in ("saturn", "sun"):
            karaka_eval = self._evaluate_d10_planet_condition(karaka, placements, d10_house_lords)
            if not karaka_eval["planet"]:
                continue
            measured_signals += 1
            if karaka_eval["quality"] == "strong":
                score += 0.35
                factors.append(f"{karaka.capitalize()} karaka is strong in D10.")
            elif karaka_eval["quality"] == "weak":
                score -= 0.35
                factors.append(f"{karaka.capitalize()} karaka is weak in D10.")
            else:
                factors.append(f"{karaka.capitalize()} karaka condition is neutral in D10.")

        if measured_signals == 0:
            return {
                "status": "neutral",
                "factors": ["D10 career signals are insufficient, using neutral fallback."],
                "multiplier": 1.0,
                "score": 0.0,
            }

        if score >= 1.15:
            status = "confirm"
            multiplier = 1.12
        elif score <= -0.85:
            status = "conflict"
            multiplier = 0.86
        else:
            status = "neutral"
            multiplier = 1.0

        return {
            "status": status,
            "factors": factors[:10],
            "multiplier": multiplier,
            "score": round(score, 3),
            "signals_considered": measured_signals,
        }

    def get_current_dasha_context(
        self,
        dasha_data: Any,
        *,
        reference_date: date | None = None,
    ) -> Dict[str, Any]:
        """
        Resolves current Mahadasha and Antardasha from available dasha payload.
        """
        today = reference_date or date.today()
        timeline = self._extract_timeline_rows(dasha_data)
        current = self._find_current_dasha_period(timeline, today)
        if not current:
            return {"mahadasha": None, "antardasha": None}

        antardasha = current.get("antardasha")
        if not antardasha:
            sub_periods = current.get("sub_periods")
            if isinstance(sub_periods, (list, tuple)):
                active_sub = self._find_current_dasha_period(sub_periods, today)
                if active_sub:
                    antardasha = active_sub.get("planet")

        return {
            "mahadasha": current.get("planet"),
            "antardasha": antardasha,
        }

    def get_dasha_activation(
        self,
        chart: Any,
        current_dasha: Any,
        prediction_context: Any,
    ) -> Dict[str, Any]:
        """Delegates Dasha Activation Index computation to the dasha engine."""
        return self._dasha_engine.get_dasha_activation(chart, current_dasha, prediction_context)

    def get_house_area(self, house: Any) -> str:
        try:
            house_num = int(house)
        except (TypeError, ValueError):
            return "general"
        return self.HOUSE_AREA_MAP.get(house_num, "general")

    def extract_prediction_context(self, yoga: Any, chart_data: Any) -> Dict[str, Any]:
        yoga_name = str(self._read_value(yoga, "id", self._read_value(yoga, "yoga", "")) or "").strip()
        strength = str(
            self._read_value(yoga, "strength_level", self._read_value(yoga, "strength", "medium")) or "medium"
        ).strip().lower()
        if strength not in {"strong", "medium", "weak"}:
            strength = "medium"

        house = self._coerce_house(
            self._read_value(
                yoga,
                "house",
                self._read_value(yoga, "to_house", self._read_value(yoga, "from_house")),
            )
        )
        key_planets = self._normalize_planet_list(self._read_value(yoga, "key_planets", []))
        if house is None:
            for planet in key_planets:
                house = self._resolve_planet_house(chart_data, planet)
                if house is not None:
                    break

        house_lord_details = self.get_house_lord_details(chart_data)
        house_lord = house_lord_details.get(house) if house is not None else None

        area = self.get_house_area(house)
        return {
            "yoga": yoga_name,
            "house": house,
            "area": area,
            "karakas": self.get_karakas(area),
            "strength": strength,
            "house_lord": house_lord,
            "house_lord_details": house_lord_details,
        }

    def get_house_lord_details(self, chart_data: Any, lagna_sign: str | None = None) -> Dict[int, Dict[str, Any]]:
        """
        Returns house-lord diagnostics (placement/dignity/affliction) for the current chart.
        """
        from core.engines.astrology_engine import get_house_lord_details as _get_house_lord_details

        return _get_house_lord_details(chart_data, lagna_sign=lagna_sign)

    def generate_contextual_prediction(
        self,
        yoga: Any,
        chart_data: Any,
        language: str | None = None,
    ) -> Dict[str, str]:
        context = self.extract_prediction_context(yoga, chart_data)
        strength = {
            "level": context.get("strength", "medium"),
            "score": self._read_value(yoga, "strength_score", None),
        }
        return self.generate_contextual(
            chart=chart_data,
            yoga=yoga,
            strength=strength,
            language=language,
        )

    def generate_contextual(
        self,
        chart: Any,
        yoga: Any,
        strength: Any,
        language: str | None = None,
    ) -> Dict[str, str]:
        normalized_language = self._normalize_language(language)
        context = self.extract_prediction_context(yoga, chart)
        yoga_name = str(context.get("yoga", "")).strip()
        area = str(context.get("area", "general")).strip() or "general"
        strength_level = self._normalize_strength_level(strength, fallback=context.get("strength", "medium"))

        area_text = self._build_area_text(area, language=normalized_language)
        strength_text = self._build_strength_text(strength_level, language=normalized_language)
        base_text = self.get_prediction(yoga_name, normalized_language)
        combined = " ".join(part for part in [area_text, strength_text, base_text] if part).strip()

        return {
            "area": area,
            "text": combined,
            "yoga": yoga_name,
            "strength": strength_level,
            "house": context.get("house"),
            "house_lord": context.get("house_lord"),
        }

    def build_bhava_lord_karaka_predictions(
        self,
        chart_data: Any,
        *,
        language: str | None = None,
        house_lord_details: Dict[int, Dict[str, Any]] | None = None,
        planet_strength: Mapping[str, Any] | None = None,
    ) -> list[Dict[str, Any]]:
        """
        Builds area predictions from Bhava + house-lord + karaka diagnostics.
        """
        normalized_language = self._normalize_language(language)
        from core.engines.astrology_engine import resolve_lagna_sign
        from core.engines.functional_nature import FunctionalNatureEngine

        lagna_sign = resolve_lagna_sign(chart_data)
        if not lagna_sign:
            return []

        details = house_lord_details if isinstance(house_lord_details, dict) else self.get_house_lord_details(chart_data)
        functional_roles = (
            FunctionalNatureEngine().get_planet_roles(lagna_sign)
            if lagna_sign
            else {}
        )
        planet_diagnostics = self._planet_diagnostics_from_house_lords(details)
        strength_payload = self._normalize_planet_strength_payload(planet_strength)

        predictions: list[Dict[str, Any]] = []
        for area, config in self.BHAVA_AREA_FRAMEWORK.items():
            area_payload = self._build_area_prediction_payload(
                area=area,
                config=config,
                house_lord_details=details,
                planet_diagnostics=planet_diagnostics,
                planet_strength=strength_payload,
                lagna_sign=lagna_sign,
                functional_roles=functional_roles,
                language=normalized_language,
            )
            if area_payload is not None:
                predictions.append(area_payload)

        return predictions

    def _build_area_prediction_payload(
        self,
        *,
        area: str,
        config: Dict[str, Any],
        house_lord_details: Dict[int, Dict[str, Any]],
        planet_diagnostics: Dict[str, Dict[str, Any]],
        planet_strength: Dict[str, Dict[str, Any]],
        lagna_sign: str | None,
        functional_roles: Dict[str, str],
        language: str,
    ) -> Dict[str, Any] | None:
        houses = [int(h) for h in config.get("houses", []) if str(h).strip().isdigit()]
        karakas = self.get_karakas(area)
        if not karakas:
            karakas = self._normalize_planet_list(config.get("karakas", []))
        if not houses:
            return None

        house_parts: list[str] = []
        trace_lines: list[str] = [f"Area framework: {area} via houses {houses} and karakas {karakas}."]
        lord_scores: list[float] = []
        involved_planets: list[str] = []
        karaka_status: list[Dict[str, Any]] = []

        for house in houses:
            house_row = house_lord_details.get(house, {})
            lord = str(house_row.get("lord", "")).strip().lower()
            if lord:
                involved_planets.append(lord)
            lord_eval = self._evaluate_house_lord_condition(house, house_row)
            lord_scores.append(lord_eval["score"])
            house_parts.append(lord_eval["text"])
            trace_lines.extend(lord_eval["trace"])

        karaka_parts: list[str] = []
        karaka_scores: list[float] = []
        for karaka in karakas:
            if karaka:
                involved_planets.append(karaka)
            karaka_diag = planet_diagnostics.get(karaka, {})
            karaka_eval = self._evaluate_karaka_condition(
                karaka,
                karaka_diag,
                strength_payload=planet_strength.get(karaka, {}),
                functional_role=functional_roles.get(karaka, "neutral"),
            )
            karaka_scores.append(karaka_eval["score"])
            karaka_parts.append(karaka_eval["text"])
            trace_lines.extend(karaka_eval["trace"])
            if isinstance(karaka_eval.get("karaka_status"), dict):
                karaka_status.append(dict(karaka_eval["karaka_status"]))

        karaka_modifier_payload = self._compute_area_karaka_modifier(
            area=area,
            karaka_status=karaka_status,
        )
        karaka_modifier = self._clamp_karaka_modifier(
            self._coerce_float(karaka_modifier_payload.get("karaka_modifier"), 1.0)
        )
        karaka_impact = karaka_modifier_payload.get("karaka_impact", [])
        if isinstance(karaka_impact, list):
            trace_lines.extend(str(line).strip() for line in karaka_impact if str(line).strip())
        trace_lines.append(
            f"Karaka moderation: modifier={karaka_modifier:.3f} (bounded {self._KARAKA_MODIFIER_MIN:.1f}-{self._KARAKA_MODIFIER_MAX:.1f})."
        )

        lord_average = sum(lord_scores) / len(lord_scores) if lord_scores else 0.0
        karaka_average = sum(karaka_scores) / len(karaka_scores) if karaka_scores else 0.0
        total_score = round((0.7 * lord_average) + (0.3 * karaka_average), 3)

        if total_score >= 0.45:
            effect = "positive"
            confidence = "high" if total_score >= 1.25 else "medium"
            lead = f"{config.get('label', area.title())} shows strength because"
        elif total_score <= -0.25:
            effect = "negative"
            confidence = "high" if total_score <= -1.0 else "medium"
            lead = f"{config.get('label', area.title())} faces strain because"
        else:
            effect = "positive"
            confidence = "low"
            lead = f"{config.get('label', area.title())} gives mixed indications because"

        weight = round(max(0.7, min(2.8, 1.0 + abs(total_score))), 2)
        reasoning_sentence = self._compose_area_reasoning(
            lead=lead,
            house_parts=house_parts,
            karaka_parts=karaka_parts,
        )
        trace_lines.append(
            f"Combined area score={total_score:.3f}; effect={effect}; confidence={confidence}; weight={weight:.2f}."
        )

        unique_roles: list[Dict[str, str]] = []
        seen_roles: set[str] = set()
        for planet in involved_planets:
            normalized_planet = str(planet or "").strip().lower()
            if not normalized_planet:
                continue
            role = str(functional_roles.get(normalized_planet, "neutral")).strip().lower() or "neutral"
            signature = f"{normalized_planet}:{role}"
            if signature in seen_roles:
                continue
            seen_roles.add(signature)
            unique_roles.append({"planet": normalized_planet, "role": role})

        return {
            "text": reasoning_sentence,
            "category": area,
            "effect": effect,
            "weight": weight,
            "result_key": f"bhava_{area}_reasoning",
            "rule_confidence": confidence,
            "trace": trace_lines,
            "functional_lagna": lagna_sign,
            "functional_roles": unique_roles,
            "karaka_status": karaka_status,
            "karaka_modifier": round(karaka_modifier, 3),
            "karaka_impact": (
                [str(line).strip() for line in karaka_impact if str(line).strip()]
                if isinstance(karaka_impact, list)
                else []
            ),
        }

    @staticmethod
    def _compose_area_reasoning(lead: str, house_parts: list[str], karaka_parts: list[str]) -> str:
        house_summary = "; ".join(part for part in house_parts if part).strip()
        karaka_summary = "; ".join(part for part in karaka_parts if part).strip()

        pieces = [str(lead or "").strip()]
        if house_summary:
            pieces.append(house_summary)
        if karaka_summary:
            pieces.append(f"Karaka condition: {karaka_summary}")

        sentence = " ".join(part for part in pieces if part).strip()
        if sentence and not sentence.endswith("."):
            sentence += "."
        return sentence

    def _evaluate_house_lord_condition(self, house: int, house_row: Dict[str, Any]) -> Dict[str, Any]:
        lord = str(house_row.get("lord", "")).strip().lower() or "unknown"
        placement = house_row.get("placement", {}) if isinstance(house_row.get("placement"), dict) else {}
        dignity_info = house_row.get("dignity", {}) if isinstance(house_row.get("dignity"), dict) else {}
        afflictions = house_row.get("affliction_flags", {}) if isinstance(house_row.get("affliction_flags"), dict) else {}

        placement_house = self._coerce_house(placement.get("house"))
        placement_sign = str(placement.get("sign", "")).strip().lower()
        dignity = str(dignity_info.get("classification", "neutral")).strip().lower() or "neutral"

        score = self._DIGNITY_SCORE.get(dignity, 0.0)
        trace = [f"House {house}: lord={lord}, placement_house={placement_house}, dignity={dignity}."]

        if placement_house in {1, 4, 5, 7, 9, 10, 11}:
            score += 0.6
            placement_quality = "supportive placement"
        elif placement_house in {6, 8, 12}:
            score -= 0.7
            placement_quality = "challenging placement"
        else:
            placement_quality = "moderate placement"

        affliction_clauses: list[str] = []
        if bool(afflictions.get("conjunct_malefic")):
            score -= 0.45
            conjunct_planets = afflictions.get("malefic_conjunct_planets", [])
            affliction_clauses.append(
                "conjunct malefic "
                + (", ".join(conjunct_planets) if conjunct_planets else "planet(s)")
            )
        if bool(afflictions.get("malefic_aspect")):
            score -= 0.4
            aspecting_planets = afflictions.get("malefic_aspecting_planets", [])
            affliction_clauses.append(
                "aspected by malefic "
                + (", ".join(aspecting_planets) if aspecting_planets else "planet(s)")
            )
        if bool(afflictions.get("combust")):
            score -= 0.55
            affliction_clauses.append("combust")

        score = round(score, 3)
        text = (
            f"{house}th lord {lord.capitalize()} is in {placement_house}th house"
            if placement_house is not None
            else f"{house}th lord {lord.capitalize()} has unavailable placement"
        )
        if placement_sign:
            text += f" ({placement_sign.capitalize()})"
        text += f", with {dignity} dignity and {placement_quality}"
        if affliction_clauses:
            text += ", though " + " and ".join(affliction_clauses)
        text += "."

        trace.append(f"House {house} lord score contribution={score:.3f}.")
        return {"score": score, "text": text, "trace": trace}

    def _evaluate_karaka_condition(
        self,
        karaka: str,
        diagnostics: Dict[str, Any],
        *,
        strength_payload: Mapping[str, Any] | None = None,
        functional_role: Any = "neutral",
    ) -> Dict[str, Any]:
        normalized_karaka = str(karaka or "").strip().lower() or "unknown"
        normalized_role = self._normalize_functional_role(functional_role)

        if not diagnostics:
            text = f"{normalized_karaka.capitalize()} karaka condition is unavailable"
            status = {
                "planet": normalized_karaka,
                "karaka_planet": normalized_karaka,
                "strength_status": self._resolve_strength_status(
                    normalized_karaka,
                    strength_payload if isinstance(strength_payload, Mapping) else {},
                    "neutral",
                ),
                "dignity": "unknown",
                "functional_nature": normalized_role,
                "affliction_flags": {},
                "contribution": "neutral",
                "reasoning": text + ".",
            }
            return {"score": 0.0, "text": text + ".", "trace": [text + "."], "karaka_status": status}

        placement_house = self._coerce_house(diagnostics.get("placement_house"))
        placement_sign = str(diagnostics.get("placement_sign", "")).strip().lower()
        dignity = str(diagnostics.get("dignity", "neutral")).strip().lower() or "neutral"
        afflictions = self._normalize_affliction_flags(diagnostics.get("affliction_flags"))
        strength_status = self._resolve_strength_status(
            normalized_karaka,
            strength_payload if isinstance(strength_payload, Mapping) else {},
            dignity,
        )

        score = self._DIGNITY_SCORE.get(dignity, 0.0) * 0.9
        if placement_house in {1, 4, 5, 7, 9, 10, 11}:
            score += 0.35
            placement_quality = "supportive placement"
        elif placement_house in {6, 8, 12}:
            score -= 0.45
            placement_quality = "challenging placement"
        else:
            placement_quality = "moderate placement"

        if strength_status == "strong":
            score += 0.24
        elif strength_status == "weak":
            score -= 0.24

        role_modifier = {
            "yogakaraka": 0.18,
            "benefic": 0.1,
            "neutral": 0.0,
            "malefic": -0.12,
        }.get(normalized_role, 0.0)
        score += role_modifier

        affliction_clauses: list[str] = []
        if bool(afflictions.get("conjunct_malefic")):
            score -= 0.3
            affliction_clauses.append("conjunct malefic influence")
        if bool(afflictions.get("malefic_aspect")):
            score -= 0.28
            affliction_clauses.append("malefic aspect")
        if bool(afflictions.get("combust")):
            score -= 0.35
            affliction_clauses.append("combust")

        score = round(score, 3)
        if score >= 0.45:
            contribution = "supportive"
        elif score <= -0.3:
            contribution = "adverse"
        else:
            contribution = "neutral"

        text = f"{normalized_karaka.capitalize()} is in {placement_house}th house" if placement_house is not None else f"{normalized_karaka.capitalize()} placement is unavailable"
        if placement_sign:
            text += f" ({placement_sign.capitalize()})"
        text += (
            f", with {dignity} dignity and {placement_quality}"
            f"; strength is {strength_status}"
            f"; functional nature is {normalized_role}"
        )
        if affliction_clauses:
            text += ", with " + " and ".join(affliction_clauses)
        text += f". Contribution: {contribution}."

        trace = [
            (
                f"Karaka {normalized_karaka}: strength={strength_status}, role={normalized_role}, dignity={dignity}, "
                f"afflicted={bool(afflictions.get('is_afflicted', False))}, score contribution={score:.3f}, "
                f"contribution={contribution}."
            )
        ]
        karaka_status = {
            "planet": normalized_karaka,
            "karaka_planet": normalized_karaka,
            "strength_status": strength_status,
            "dignity": dignity,
            "functional_nature": normalized_role,
            "affliction_flags": afflictions,
            "contribution": contribution,
            "reasoning": text,
        }
        return {"score": score, "text": text, "trace": trace, "karaka_status": karaka_status}

    @staticmethod
    def _planet_diagnostics_from_house_lords(
        house_lord_details: Dict[int, Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        diagnostics: Dict[str, Dict[str, Any]] = {}
        for row in (house_lord_details or {}).values():
            if not isinstance(row, dict):
                continue
            lord = str(row.get("lord", "")).strip().lower()
            if not lord or lord in diagnostics:
                continue

            placement = row.get("placement", {}) if isinstance(row.get("placement"), dict) else {}
            dignity = row.get("dignity", {}) if isinstance(row.get("dignity"), dict) else {}
            afflictions = row.get("affliction_flags", {}) if isinstance(row.get("affliction_flags"), dict) else {}

            diagnostics[lord] = {
                "placement_house": placement.get("house"),
                "placement_sign": placement.get("sign"),
                "dignity": dignity.get("classification", "neutral"),
                "affliction_flags": afflictions,
            }
        return diagnostics

    @classmethod
    def _normalize_karaka_registry(cls, raw_registry: Mapping[str, Any] | None) -> Dict[str, list[str]]:
        merged: Dict[str, Any] = dict(cls.DEFAULT_KARAKA_REGISTRY)
        if isinstance(raw_registry, Mapping):
            for raw_area, raw_karakas in raw_registry.items():
                area = str(raw_area or "").strip().lower()
                if not area:
                    continue
                merged[area] = raw_karakas

        normalized_registry: Dict[str, list[str]] = {}
        for raw_area, raw_karakas in merged.items():
            area = cls.AREA_REGISTRY_ALIASES.get(str(raw_area or "").strip().lower(), str(raw_area or "").strip().lower())
            if not area:
                continue
            karakas = cls._normalize_planet_list(raw_karakas)
            if not karakas:
                continue
            normalized_registry[area] = karakas
        return normalized_registry

    @staticmethod
    def _normalize_functional_role(role: Any) -> str:
        normalized = str(role or "neutral").strip().lower() or "neutral"
        if normalized in {"yogakaraka", "benefic", "neutral", "malefic"}:
            return normalized
        return "neutral"

    @staticmethod
    def _normalize_affliction_flags(raw_flags: Any) -> Dict[str, Any]:
        flags = raw_flags if isinstance(raw_flags, Mapping) else {}
        normalized = {
            "conjunct_malefic": bool(flags.get("conjunct_malefic", False)),
            "malefic_aspect": bool(flags.get("malefic_aspect", False)),
            "combust": bool(flags.get("combust", False)),
        }
        normalized["is_afflicted"] = (
            bool(flags.get("is_afflicted", False))
            or normalized["conjunct_malefic"]
            or normalized["malefic_aspect"]
            or normalized["combust"]
        )
        if isinstance(flags.get("malefic_conjunct_planets"), list):
            normalized["malefic_conjunct_planets"] = [
                str(planet).strip().lower()
                for planet in flags.get("malefic_conjunct_planets", [])
                if str(planet).strip()
            ]
        if isinstance(flags.get("malefic_aspecting_planets"), list):
            normalized["malefic_aspecting_planets"] = [
                str(planet).strip().lower()
                for planet in flags.get("malefic_aspecting_planets", [])
                if str(planet).strip()
            ]
        return normalized

    def _compute_area_karaka_modifier(
        self,
        *,
        area: str,
        karaka_status: list[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if not isinstance(karaka_status, list) or not karaka_status:
            return {
                "karaka_modifier": 1.0,
                "karaka_impact": [f"{str(area or 'general').capitalize()} has no karaka diagnostics; neutral moderation applied."],
                "details": [],
            }

        seen_counts: Dict[str, int] = {}
        weighted_total = 0.0
        weight_sum = 0.0
        min_modifier = self._KARAKA_MODIFIER_MAX
        details: list[Dict[str, Any]] = []
        impact_lines: list[str] = []

        for entry in karaka_status:
            if not isinstance(entry, dict):
                continue
            planet = normalize_planet_name(entry.get("planet") or entry.get("karaka_planet")) or "unknown"
            contribution = str(entry.get("contribution", "neutral")).strip().lower() or "neutral"
            if contribution not in self._KARAKA_CONTRIBUTION_BASE:
                contribution = "neutral"

            strength_status = str(entry.get("strength_status", "medium")).strip().lower() or "medium"
            if strength_status not in {"strong", "medium", "weak"}:
                strength_status = "medium"
            dignity = str(entry.get("dignity", "neutral")).strip().lower() or "neutral"
            afflictions = self._normalize_affliction_flags(entry.get("affliction_flags"))

            base_modifier = self._KARAKA_CONTRIBUTION_BASE[contribution]
            if strength_status == "strong":
                base_modifier += 0.04
            elif strength_status == "weak":
                base_modifier -= 0.08

            if dignity == "exalted":
                base_modifier += 0.05
            elif dignity == "own":
                base_modifier += 0.03
            elif dignity == "friendly":
                base_modifier += 0.01
            elif dignity == "enemy":
                base_modifier -= 0.04
            elif dignity == "debilitated":
                base_modifier -= 0.08

            affliction_penalty = 0.0
            if bool(afflictions.get("is_afflicted")):
                affliction_penalty += 0.08
            if bool(afflictions.get("conjunct_malefic")):
                affliction_penalty += 0.02
            if bool(afflictions.get("malefic_aspect")):
                affliction_penalty += 0.02
            if bool(afflictions.get("combust")):
                affliction_penalty += 0.03
            base_modifier -= min(0.15, affliction_penalty)

            occurrence = seen_counts.get(planet, 0)
            seen_counts[planet] = occurrence + 1
            dedupe_factor = round(1.0 / float(2 ** occurrence), 6)
            planet_modifier = self._clamp_karaka_modifier(base_modifier)
            weighted_total += planet_modifier * dedupe_factor
            weight_sum += dedupe_factor
            min_modifier = min(min_modifier, planet_modifier)

            trend = "supporting" if planet_modifier > 1.03 else "reducing" if planet_modifier < 0.97 else "balancing"
            reason_bits: list[str] = [
                f"{planet.capitalize()} {contribution}",
                f"strength {strength_status}",
                f"dignity {dignity}",
            ]
            if bool(afflictions.get("is_afflicted")):
                reason_bits.append("afflicted")
            if dedupe_factor < 1.0:
                reason_bits.append(f"overlap weight {dedupe_factor:.2f}")

            impact_lines.append(
                f"{planet.capitalize()} {contribution} -> {trend} {str(area or 'general').lower()} outcome ({', '.join(reason_bits)})."
            )
            details.append(
                {
                    "planet": planet,
                    "modifier": round(planet_modifier, 3),
                    "dedupe_factor": dedupe_factor,
                    "contribution": contribution,
                    "strength_status": strength_status,
                    "dignity": dignity,
                    "is_afflicted": bool(afflictions.get("is_afflicted")),
                }
            )

        if weight_sum <= 0.0:
            return {
                "karaka_modifier": 1.0,
                "karaka_impact": [f"{str(area or 'general').capitalize()} karaka diagnostics are inconclusive; neutral moderation applied."],
                "details": [],
            }

        weighted_average = weighted_total / weight_sum
        blended_modifier = self._clamp_karaka_modifier((0.7 * weighted_average) + (0.3 * min_modifier))
        if not impact_lines:
            impact_lines.append(
                f"{str(area or 'general').capitalize()} karaka diagnostics remain balanced; neutral moderation applied."
            )
        impact_lines.append(
            f"Karaka moderation blended via weighted-average + min-dominance => {blended_modifier:.3f}."
        )

        return {
            "karaka_modifier": round(blended_modifier, 3),
            "karaka_impact": impact_lines[:8],
            "details": details,
        }

    def _clamp_karaka_modifier(self, value: Any) -> float:
        return max(
            self._KARAKA_MODIFIER_MIN,
            min(self._KARAKA_MODIFIER_MAX, self._coerce_float(value, 1.0) or 1.0),
        )

    def _resolve_strength_status(
        self,
        planet: str,
        strength_payload: Mapping[str, Any],
        dignity: str,
    ) -> str:
        raw_level = str(strength_payload.get("level", "")).strip().lower()
        if raw_level in {"strong", "medium", "weak"}:
            return raw_level

        raw_score = strength_payload.get("score")
        if raw_score is not None:
            score = self._coerce_float(raw_score, default=-1.0)
            if score >= 70.0:
                return "strong"
            if score >= 40.0:
                return "medium"
            if score >= 0.0:
                return "weak"

        raw_total = strength_payload.get("total")
        if raw_total is not None:
            total = self._coerce_float(raw_total, default=-1.0)
            if total >= 0.0:
                target = self._PLANET_STRENGTH_TARGETS.get(planet, 300.0)
                percent_score = max(0.0, min(100.0, (total / target) * 75.0))
                if percent_score >= 70.0:
                    return "strong"
                if percent_score >= 40.0:
                    return "medium"
                return "weak"

        if dignity in self._STRONG_DIGNITIES:
            return "strong"
        if dignity in self._WEAK_DIGNITIES:
            return "weak"
        return "medium"

    @classmethod
    def _normalize_planet_strength_payload(cls, raw_strength: Mapping[str, Any] | None) -> Dict[str, Dict[str, Any]]:
        if not isinstance(raw_strength, Mapping):
            return {}

        normalized: Dict[str, Dict[str, Any]] = {}
        for raw_planet, payload in raw_strength.items():
            planet = normalize_planet_name(raw_planet)
            if not planet:
                continue

            if isinstance(payload, Mapping):
                normalized[planet] = dict(payload)
                continue

            row: Dict[str, Any] = {}
            level = getattr(payload, "level", None)
            score = getattr(payload, "score", None)
            breakdown = getattr(payload, "breakdown", None)
            if level is not None:
                row["level"] = level
            if score is not None:
                row["score"] = score
            if isinstance(breakdown, Mapping) and "total" in breakdown:
                row["total"] = breakdown.get("total")
            if row:
                normalized[planet] = row
        return normalized

    def _load_meanings(self) -> Dict[str, Dict[str, Any]]:
        if self._meanings is not None:
            return self._meanings

        try:
            payload = json.loads(self.meanings_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}

        if not isinstance(payload, dict):
            payload = {}

        self._meanings = {
            str(key).strip(): value
            for key, value in payload.items()
            if isinstance(value, dict)
        }
        return self._meanings

    @staticmethod
    def _read_value(payload: Any, key: str, default: Any = None) -> Any:
        if isinstance(payload, dict):
            return payload.get(key, default)
        return getattr(payload, key, default)

    @staticmethod
    def _coerce_house(raw_house: Any) -> int | None:
        try:
            house = int(raw_house)
        except (TypeError, ValueError):
            return None
        if 1 <= house <= 12:
            return house
        return None

    @staticmethod
    def _normalize_planet_list(planets: Any) -> list[str]:
        if not isinstance(planets, (list, tuple, set)):
            return []
        normalized: list[str] = []
        for planet in planets:
            planet_id = normalize_planet_name(planet)
            if planet_id and planet_id not in normalized:
                normalized.append(planet_id)
        return normalized

    def _build_dasha_activation_context(
        self,
        *,
        yoga: Any,
        chart_data: Any,
        prediction_context: Mapping[str, Any] | None,
        yoga_planets: list[str],
    ) -> Dict[str, Any]:
        context: Dict[str, Any] = dict(prediction_context or {})
        context.setdefault("yoga_planets", yoga_planets)

        key_planets = self._normalize_planet_list(self._read_value(yoga, "key_planets", []))
        if key_planets:
            merged_planets = list(context.get("yoga_planets", [])) if isinstance(context.get("yoga_planets"), list) else []
            for planet in key_planets:
                if planet not in merged_planets:
                    merged_planets.append(planet)
            context["yoga_planets"] = merged_planets
            context.setdefault("key_planets", merged_planets)

        relevant_houses = context.get("relevant_houses")
        if not isinstance(relevant_houses, (list, tuple, set)):
            house = self._coerce_house(
                self._read_value(
                    yoga,
                    "house",
                    self._read_value(yoga, "to_house", self._read_value(yoga, "from_house")),
                )
            )
            relevant_houses = [house] if house is not None else []
        context["relevant_houses"] = [h for h in relevant_houses if self._coerce_house(h) is not None]

        area = str(context.get("area", self._read_value(yoga, "area", "")) or "").strip().lower()
        if not area and context["relevant_houses"]:
            area = self.get_house_area(context["relevant_houses"][0])
        context["area"] = area or "general"

        if "karakas" not in context:
            context["karakas"] = self.get_karakas(context["area"])

        if "house_lord_details" not in context and chart_data is not None:
            try:
                context["house_lord_details"] = self.get_house_lord_details(chart_data)
            except Exception:
                context["house_lord_details"] = {}

        if "functional_roles" not in context:
            context["functional_roles"] = self._read_value(yoga, "functional_roles", {})

        if "planet_strength" not in context:
            raw_strength = self._read_value(yoga, "planet_strength", self._read_value(yoga, "strength_payload", {}))
            context["planet_strength"] = raw_strength if isinstance(raw_strength, Mapping) else {}

        context.setdefault(
            "yoga_strength",
            str(self._read_value(yoga, "strength_level", self._read_value(yoga, "strength", "medium")) or "medium")
            .strip()
            .lower(),
        )
        context.setdefault(
            "yoga_state",
            str(self._read_value(yoga, "state", "strong") or "strong").strip().lower(),
        )
        return context

    @staticmethod
    def _coerce_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _resolve_highest_activation_level(self, first: str, second: str) -> str:
        first_level = str(first or "low").strip().lower() or "low"
        second_level = str(second or "low").strip().lower() or "low"
        if self._ACTIVATION_LEVEL_ORDER.get(first_level, 0) >= self._ACTIVATION_LEVEL_ORDER.get(second_level, 0):
            return first_level
        return second_level

    def _compute_activation_multiplier(self, activation_score: float, activation_level: str) -> float:
        level = str(activation_level or "low").strip().lower() or "low"
        bounded_score = max(0.0, min(100.0, activation_score))
        if level == "high":
            multiplier = 1.12 + min(0.18, (bounded_score / 100.0) * 0.18)
        elif level == "medium":
            multiplier = 1.03 + min(0.08, (bounded_score / 100.0) * 0.08)
        else:
            multiplier = 0.88 + min(0.1, (bounded_score / 100.0) * 0.1)
        return round(max(0.85, min(1.3, multiplier)), 3)

    @staticmethod
    def _extract_dasha_evidence(contributing_factors: Any) -> list[str]:
        evidence: list[str] = []
        if not isinstance(contributing_factors, (list, tuple)):
            return evidence

        for factor in contributing_factors:
            if not isinstance(factor, Mapping):
                continue
            rows = factor.get("evidence", [])
            if not isinstance(rows, (list, tuple)):
                continue
            for line in rows:
                text = str(line or "").strip()
                if text and text not in evidence:
                    evidence.append(text)
        return evidence[:12]

    def _evaluate_d10_planet_condition(
        self,
        planet: Any,
        placements: Any,
        house_lord_details: Any,
    ) -> Dict[str, Any]:
        planet_id = normalize_planet_name(planet)
        if not planet_id:
            return {"planet": "", "quality": "neutral", "house": None, "dignity": "neutral", "afflicted": False}

        placement = placements.get(planet_id, {}) if isinstance(placements, Mapping) else {}
        sign = str(placement.get("sign", "")).strip().lower()
        house = self._coerce_house(placement.get("house"))
        dignity = DignityEngine.get_dignity(planet_id, sign) if sign else "neutral"

        afflicted = False
        if isinstance(house_lord_details, Mapping):
            for row in house_lord_details.values():
                if not isinstance(row, Mapping):
                    continue
                if normalize_planet_name(row.get("lord")) != planet_id:
                    continue
                afflictions = row.get("affliction_flags", {}) if isinstance(row.get("affliction_flags"), Mapping) else {}
                if bool(afflictions.get("is_afflicted")):
                    afflicted = True
                    break

        strong_houses = {1, 4, 5, 7, 9, 10, 11}
        weak_houses = {6, 8, 12}
        strong_dignities = {"exalted", "own", "friendly"}
        weak_dignities = {"debilitated", "enemy"}

        has_strong_signal = (house in strong_houses) or (dignity in strong_dignities)
        has_weak_signal = (house in weak_houses) or (dignity in weak_dignities) or afflicted

        if has_weak_signal:
            quality = "weak"
        elif has_strong_signal:
            quality = "strong"
        else:
            quality = "neutral"

        return {
            "planet": planet_id,
            "quality": quality,
            "house": house,
            "dignity": dignity,
            "afflicted": afflicted,
        }

    def _resolve_primary_house_lord(
        self,
        relevant_houses: list[int],
        explicit_house_lord: Any,
        house_lord_details: Any,
    ) -> str:
        if isinstance(explicit_house_lord, Mapping):
            lord = normalize_planet_name(explicit_house_lord.get("lord"))
            if lord:
                return lord
        explicit_text = normalize_planet_name(explicit_house_lord)
        if explicit_text:
            return explicit_text

        if not isinstance(house_lord_details, Mapping):
            return ""
        for house in relevant_houses:
            row = house_lord_details.get(house)
            if not isinstance(row, Mapping):
                continue
            lord = normalize_planet_name(row.get("lord"))
            if lord:
                return lord
        return ""

    def _extract_transit_matrix(self, transit_data: Any) -> Dict[str, Dict[str, Any]]:
        if not isinstance(transit_data, Mapping):
            return {}

        matrix = transit_data.get("transit_matrix")
        if isinstance(matrix, Mapping):
            normalized: Dict[str, Dict[str, Any]] = {}
            for planet, row in matrix.items():
                planet_id = normalize_planet_name(planet)
                if not planet_id or not isinstance(row, Mapping):
                    continue
                normalized[planet_id] = dict(row)
            if normalized:
                return normalized

        from_lagna = transit_data.get("from_lagna", {})
        from_moon = transit_data.get("from_moon", {})
        if not isinstance(from_lagna, Mapping) and not isinstance(from_moon, Mapping):
            return {}

        planets = set()
        if isinstance(from_lagna, Mapping):
            planets.update(from_lagna.keys())
        if isinstance(from_moon, Mapping):
            planets.update(from_moon.keys())

        rebuilt: Dict[str, Dict[str, Any]] = {}
        for raw_planet in planets:
            planet = normalize_planet_name(raw_planet)
            if not planet:
                continue
            rebuilt[planet] = {
                "transit_planet": planet,
                "from_lagna": dict(from_lagna.get(raw_planet, {})) if isinstance(from_lagna, Mapping) else {},
                "from_moon": dict(from_moon.get(raw_planet, {})) if isinstance(from_moon, Mapping) else {},
            }
        return rebuilt

    def _coerce_chart_rows_for_varga(self, chart_data: Any) -> list[Dict[str, Any]]:
        if isinstance(chart_data, (list, tuple)):
            return [row for row in chart_data]

        placements = getattr(chart_data, "placements", None)
        if isinstance(placements, Mapping):
            rows: list[Dict[str, Any]] = []
            for planet_id, placement in placements.items():
                planet_name = str(getattr(placement, "planet", planet_id) or planet_id).strip()
                sign = str(getattr(placement, "sign", "")).strip()
                house = self._coerce_house(getattr(placement, "house", None))
                degree = self._coerce_float(getattr(placement, "degree", 0.0), 0.0)
                if not planet_name or not sign or house is None:
                    continue
                rows.append(
                    {
                        "planet_name": planet_name,
                        "sign": sign,
                        "house": house,
                        "degree": degree,
                    }
                )
            return rows

        return []

    def _resolve_actor_houses(self, house_lord_details: Any, actors: set[str]) -> Dict[str, int]:
        if not isinstance(house_lord_details, Mapping):
            return {}

        actor_houses: Dict[str, int] = {}
        for row in house_lord_details.values():
            if not isinstance(row, Mapping):
                continue
            lord = normalize_planet_name(row.get("lord"))
            if not lord or lord not in actors or lord in actor_houses:
                continue
            placement = row.get("placement", {}) if isinstance(row.get("placement"), Mapping) else {}
            house = self._coerce_house(placement.get("house"))
            if house is not None:
                actor_houses[lord] = house
        return actor_houses

    @staticmethod
    def _house_contact_label(transit_house: int, natal_house: int) -> str:
        if transit_house == natal_house:
            return "conjunction with"

        # Simple, explainable "aspect-like" fallback: opposite (7th) house relation.
        opposite_house = ((natal_house + 5) % 12) + 1
        if transit_house == opposite_house:
            return "opposition to"
        return ""

    def _resolve_planet_house(self, chart_data: Any, planet_name: str) -> int | None:
        placements = getattr(chart_data, "placements", None)
        if isinstance(placements, dict):
            placement = placements.get(normalize_planet_name(planet_name))
            if placement is not None:
                return self._coerce_house(getattr(placement, "house", None))

        return get_planet_house(chart_data, planet_name)

    @staticmethod
    def _normalize_strength_level(strength: Any, *, fallback: Any = "medium") -> str:
        if isinstance(strength, dict):
            candidate = strength.get("level", fallback)
        else:
            candidate = strength if strength is not None else fallback

        normalized = str(candidate or "medium").strip().lower() or "medium"
        if normalized not in {"strong", "medium", "weak"}:
            return "medium"
        return normalized

    @staticmethod
    def _extract_timeline_rows(dasha_data: Any) -> list[Dict[str, Any]]:
        if isinstance(dasha_data, dict):
            rows = dasha_data.get("timeline", [])
            return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
        if isinstance(dasha_data, list):
            return [row for row in dasha_data if isinstance(row, dict)]
        return []

    @staticmethod
    def _parse_iso_date(raw_date: Any) -> date | None:
        if not raw_date:
            return None
        try:
            return datetime.strptime(str(raw_date).strip(), "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return None

    def _find_current_dasha_period(self, periods: Any, target_date: date) -> Dict[str, Any] | None:
        if not isinstance(periods, (list, tuple)):
            return None

        sorted_periods = sorted(
            [row for row in periods if isinstance(row, dict)],
            key=lambda row: self._parse_iso_date(row.get("start")) or date.max,
        )
        for period in sorted_periods:
            start = self._parse_iso_date(period.get("start"))
            end = self._parse_iso_date(period.get("end"))
            if not start or not end:
                continue
            if start <= target_date <= end:
                return period
        return sorted_periods[-1] if sorted_periods else None

    def _build_area_text(self, area: str, *, language: str) -> str:
        if language == "hi":
            if area == "career":
                return "करियर में सफलता के संकेत हैं।"
            if area == "marriage":
                return "रिश्तों और साझेदारी में लाभ के संकेत हैं।"
            if area == "wealth":
                return "धन और आर्थिक स्थिरता में वृद्धि के संकेत हैं।"
            if area == "health":
                return "स्वास्थ्य और दिनचर्या में महत्वपूर्ण परिवर्तन दिखते हैं।"
            if area == "self":
                return "व्यक्तिगत विकास के मजबूत संकेत हैं।"
            if area == "general":
                return "जीवन में अर्थपूर्ण परिणामों के संकेत हैं।"
            return f"{area} में उल्लेखनीय परिणामों के संकेत हैं।"
        if language == "or":
            if area == "career":
                return "କ୍ୟାରିଅରରେ ସଫଳତାର ସୂଚନା ମିଳୁଛି।"
            if area == "marriage":
                return "ସମ୍ପର୍କ ଏବଂ ସହଭାଗୀତାରେ ଲାଭର ସୂଚନା ମିଳୁଛି।"
            if area == "wealth":
                return "ଧନ ଏବଂ ଆର୍ଥିକ ସ୍ଥିରତାର ବୃଦ୍ଧି ସୂଚିତ ହେଉଛି।"
            if area == "health":
                return "ସ୍ୱାସ୍ଥ୍ୟ ଏବଂ ଦୈନନ୍ଦିନ ଅଭ୍ୟାସରେ ପରିବର୍ତ୍ତନ ସୂଚିତ ହେଉଛି।"
            if area == "self":
                return "ବ୍ୟକ୍ତିଗତ ଉନ୍ନତିର ଶକ୍ତିଶାଳୀ ସୂଚନା ମିଳୁଛି।"
            if area == "general":
                return "ଜୀବନରେ ଅର୍ଥପୂର୍ଣ୍ଣ ଫଳର ସୂଚନା ମିଳୁଛି।"
            return f"{area} ରେ ଲକ୍ଷଣୀୟ ଫଳର ସୂଚନା ମିଳୁଛି।"

        if area == "career":
            return "You achieve success in career."
        if area == "marriage":
            return "You benefit in relationships and partnerships."
        if area == "wealth":
            return "You see growth in wealth and financial stability."
        if area == "health":
            return "You experience important shifts in health and routines."
        if area == "self":
            return "You experience strong personal development."
        if area == "general":
            return "You receive meaningful results in life."
        return f"You receive notable results in {area}."

    def _build_strength_text(self, strength: str, *, language: str) -> str:
        if language == "hi":
            if strength == "strong":
                return "परिणाम शक्तिशाली और स्पष्ट रूप से दिखाई देंगे।"
            if strength == "weak":
                return "परिणाम हल्के रह सकते हैं और देरी महसूस हो सकती है।"
            return "परिणाम संतुलित और स्थिर रहेंगे।"
        if language == "or":
            if strength == "strong":
                return "ଫଳ ଶକ୍ତିଶାଳୀ ଏବଂ ସ୍ପଷ୍ଟ ଭାବେ ଦେଖାଯିବ।"
            if strength == "weak":
                return "ଫଳ ମୃଦୁ ରହିପାରେ ଏବଂ ବିଳମ୍ବ ଲାଗିପାରେ।"
            return "ଫଳ ସନ୍ତୁଳିତ ଏବଂ ସ୍ଥିର ରହିବ।"

        if strength == "strong":
            return "Results are powerful and clearly visible."
        if strength == "weak":
            return "Results are mild and may feel delayed."
        return "Results are moderate and steady."

    def _normalize_language(self, language: str | None) -> str:
        normalized = str(language or self.DEFAULT_LANGUAGE).strip().lower() or self.DEFAULT_LANGUAGE
        if normalized not in self.SUPPORTED_LANGUAGES:
            return self.DEFAULT_LANGUAGE
        return normalized

    @classmethod
    def _normalize_final_layer_weights(cls, raw_weights: Mapping[str, Any] | None) -> Dict[str, float]:
        if isinstance(raw_weights, Mapping):
            candidates = {
                key: cls._coerce_float(raw_weights.get(key), cls.FINAL_LAYER_WEIGHTS[key])
                for key in cls.FINAL_LAYER_WEIGHTS
            }
        else:
            candidates = dict(cls.FINAL_LAYER_WEIGHTS)

        bounded = {
            key: max(0.0, float(candidates.get(key, 0.0)))
            for key in cls.FINAL_LAYER_WEIGHTS
        }
        total = sum(bounded.values())
        if total <= 0:
            return dict(cls.FINAL_LAYER_WEIGHTS)

        return {
            key: round(bounded[key] / total, 6)
            for key in cls.FINAL_LAYER_WEIGHTS
        }


_default_prediction_service = PredictionService()


def get_prediction(rule_key: Any, language: str | None = None) -> str:
    """Returns a localized prediction meaning for one rule key."""
    return _default_prediction_service.get_prediction(rule_key, language)


def get_prediction_weight(rule_key: Any) -> float:
    """Returns configured prediction weight for one rule key (default 0)."""
    return _default_prediction_service.get_weight(rule_key)


def get_contextual_prediction(
    yoga: Any,
    chart_data: Any,
    language: str | None = None,
) -> Dict[str, str]:
    """Returns context-aware prediction payload for one yoga."""
    return _default_prediction_service.generate_contextual_prediction(yoga, chart_data, language)


def get_conflict_resolution_priority() -> list[str]:
    """Returns M9 deterministic conflict priority."""
    return _default_prediction_service.get_conflict_resolution_priority()


def get_conflict_resolution_thresholds() -> Dict[str, float]:
    """Returns M9 deterministic conflict thresholds."""
    return _default_prediction_service.get_conflict_resolution_thresholds()
