from __future__ import annotations

from collections import defaultdict, deque
import re
import logging
from typing import Any, Dict, Iterable, Optional
from app.services.event_service import EventService
from app.services.intent_keywords import (
    INTENT_KEYWORDS,
    detect_intent,
    detect_intents,
)
from app.services.reasoning_service import ReasoningService
from app.services.timeline_service import TimelineService
from app.utils.cache import get_astrology_cache
from app.utils.logger import log_user_action

logger = logging.getLogger(__name__)
FOLLOW_UP_MARKERS = {
    "and",
    "also",
    "then",
    "next",
    "what",
    "about",
    "how",
    "why",
    "explain",
    "more",
}
SUPPORTED_LANGUAGES = {"en", "hi", "or"}


def _count_matches(tokens: list[str], keywords: Iterable[str]) -> int:
    """Counts how many keyword hits appear in the tokenized query."""
    token_set = set(tokens)
    return sum(1 for keyword in keywords if keyword in token_set)


def _clean_sentence(text: str) -> str:
    """Normalizes whitespace and ensures the text ends like a sentence."""
    cleaned = " ".join(str(text or "").split()).strip()
    if not cleaned:
        return ""
    if cleaned[-1] not in ".!?":
        cleaned += "."
    return cleaned


def _normalize_language(language: str) -> str:
    normalized = str(language or "en").strip().lower() or "en"
    if normalized not in SUPPORTED_LANGUAGES:
        return "en"
    return normalized


def _confidence_phrase(confidence: str, *, language: str = "en") -> str:
    """Maps confidence values into human-friendly language."""
    normalized = str(confidence or "").strip().lower()
    active_language = _normalize_language(language)
    if active_language == "hi":
        if normalized == "high":
            return "संकेत मजबूत हैं।"
        if normalized == "medium":
            return "संकेत सहायक हैं।"
        if normalized == "low":
            return "संकेत मौजूद हैं, लेकिन अभी हल्के हैं।"
        return "संकेत मिश्रित हैं।"
    if active_language == "or":
        if normalized == "high":
            return "ସୂଚନା ଶକ୍ତିଶାଳୀ।"
        if normalized == "medium":
            return "ସୂଚନା ସହାୟକ ଅଛି।"
        if normalized == "low":
            return "ସୂଚନା ଅଛି, କିନ୍ତୁ ଏଖଣି ହାଲୁକା।"
        return "ସୂଚନା ମିଶ୍ରିତ।"
    if normalized == "high":
        return "The indications are strong."
    if normalized == "medium":
        return "The indications are reasonably supportive."
    if normalized == "low":
        return "The indications are present but still modest."
    return "The indications are mixed."


def generate_response(intent: str, data: Dict[str, Any], *, language: str = "en") -> str:
    """
    Generates a readable horoscope answer from structured intent data.

    Expected data shape:
    {
        "prediction_summary": "...",
        "confidence": "high|medium|low",
        "timeline_hint": "..."
    }
    """
    intent_sections = data.get("intent_sections") if isinstance(data, dict) else None
    if isinstance(intent_sections, list) and len(intent_sections) > 1:
        return _generate_multi_intent_response(intent_sections, data, language=language)

    normalized_intent = str(intent or "general").strip().lower() or "general"
    normalized_language = _normalize_language(language)
    prediction_summary = _clean_sentence(data.get("prediction_summary", ""))
    timeline_hint = _clean_sentence(data.get("timeline_hint", ""))
    confidence_text = _confidence_phrase(data.get("confidence", ""), language=normalized_language)
    memory_note = _clean_sentence(data.get("memory_note", ""))

    if normalized_language == "hi":
        opener_map = {
            "career": "आपके करियर संकेत इस प्रकार हैं:",
            "marriage": "आपके संबंध और विवाह संकेत इस प्रकार हैं:",
            "finance": "आपके वित्तीय संकेत इस प्रकार हैं:",
            "health": "आपके स्वास्थ्य संकेत इस प्रकार हैं:",
            "general": "आपके प्रश्न के आधार पर ज्योतिषीय दृष्टि:",
        }
        why_label = "क्यों:"
        supporting_label = "सहायक कारक:"
        timeline_label = "समय संकेत:"
        no_context_line = "अभी विशिष्ट उत्तर के लिए पर्याप्त संरचित ज्योतिषीय संदर्भ नहीं है।"
    elif normalized_language == "or":
        opener_map = {
            "career": "ଆପଣଙ୍କ କ୍ୟାରିଅର ସୂଚନା ଏପରି ଅଛି:",
            "marriage": "ଆପଣଙ୍କ ସମ୍ପର୍କ ଓ ବିବାହ ସୂଚନା ଏପରି ଅଛି:",
            "finance": "ଆପଣଙ୍କ ଆର୍ଥିକ ସୂଚନା ଏପରି ଅଛି:",
            "health": "ଆପଣଙ୍କ ସ୍ୱାସ୍ଥ୍ୟ ସୂଚନା ଏପରି ଅଛି:",
            "general": "ଆପଣଙ୍କ ପ୍ରଶ୍ନ ଆଧାରରେ ଜ୍ୟୋତିଷୀୟ ଦୃଷ୍ଟି:",
        }
        why_label = "କାହିଁକି:"
        supporting_label = "ସମର୍ଥନ କାରକ:"
        timeline_label = "ସମୟ ସୂଚନା:"
        no_context_line = "ବିଶିଷ୍ଟ ଉତ୍ତର ପାଇଁ ଏଖଣି ପର୍ଯ୍ୟାପ୍ତ ଗଠିତ ଜ୍ୟୋତିଷ ତଥ୍ୟ ନାହିଁ।"
    else:
        opener_map = {
            "career": "Your career outlook suggests the following:",
            "marriage": "Your relationship and marriage outlook suggests the following:",
            "finance": "Your financial outlook suggests the following:",
            "health": "Your health outlook suggests the following:",
            "general": "Here is the astrological view based on your question:",
        }
        why_label = "Why:"
        supporting_label = "Supporting factors:"
        timeline_label = "Timeline hint:"
        no_context_line = "There is not enough structured astrological context yet for a specific answer."
    opener = opener_map.get(normalized_intent, opener_map["general"])

    parts = [opener]
    if prediction_summary:
        parts.append(prediction_summary)
    reasoning_rows = data.get("reasoning", []) if isinstance(data, dict) else []
    if isinstance(reasoning_rows, list) and reasoning_rows:
        first_reasoning = reasoning_rows[0] if isinstance(reasoning_rows[0], dict) else {}
        explanation = _clean_sentence(first_reasoning.get("explanation", ""))
        if explanation:
            parts.append(f"{why_label} {explanation}")
        supporting = first_reasoning.get("supporting_factors", [])
        if isinstance(supporting, list):
            supporting_clean = [_clean_sentence(item).rstrip(".") for item in supporting if _clean_sentence(item)]
            if supporting_clean:
                parts.append(f"{supporting_label} {'; '.join(supporting_clean)}.")
    parts.append(confidence_text)
    if memory_note:
        parts.append(memory_note)
    if timeline_hint:
        parts.append(f"{timeline_label} {timeline_hint}")

    if len(parts) == 2 and not prediction_summary and not timeline_hint:
        parts.append(no_context_line)

    return " ".join(parts)


def _generate_multi_intent_response(intent_sections: list[dict], data: Dict[str, Any], *, language: str = "en") -> str:
    """Builds a readable combined response for multi-intent chat queries."""
    section_texts = []
    for section in intent_sections:
        section_intent = str(section.get("intent", "general")).strip().lower() or "general"
        section_texts.append(
            generate_response(
                section_intent,
                {
                    "prediction_summary": section.get("prediction_summary", ""),
                    "confidence": section.get("confidence", ""),
                    "timeline_hint": section.get("timeline_hint", ""),
                    "reasoning": section.get("reasoning", []),
                    "memory_note": "",
                },
                language=language,
            )
        )

    memory_note = _clean_sentence(data.get("memory_note", ""))
    if memory_note:
        section_texts.append(memory_note)

    return " ".join(text for text in section_texts if text).strip()


class HoroscopeChatService:
    """
    Isolated chat-service entry point for natural-language horoscope questions.

    This service is intentionally lightweight in Step 1:
    - accepts a user question
    - detects intent
    - exposes extension points for data fetching and response generation
    """

    def __init__(
        self,
        horoscope_service: Optional[object] = None,
        ai_refiner: Optional[object] = None,
        reasoning_service: Optional[ReasoningService] = None,
        timeline_service: Optional[TimelineService] = None,
        event_service: Optional[EventService] = None,
    ):
        self.horoscope_service = horoscope_service
        self.ai_refiner = ai_refiner
        self.reasoning_service = reasoning_service or ReasoningService()
        self.timeline_service = timeline_service or TimelineService()
        self.event_service = event_service or EventService()
        self.cache = get_astrology_cache()
        self.memory: dict[int, deque[dict[str, Any]]] = defaultdict(lambda: deque(maxlen=5))
        self.last_query_by_user: dict[int, str] = {}
        self.current_language = "en"

    def set_language(self, language: str) -> None:
        self.current_language = _normalize_language(language)

    def detect_intent(self, query: str) -> str:
        """Delegates to the standalone intent detector for reuse and testing."""
        return detect_intent(query)

    def detect_intents(self, query: str) -> list[str]:
        """Delegates to the standalone multi-intent detector for reuse and testing."""
        return detect_intents(query)

    def generate_response(self, intent: str, data: Dict[str, Any], *, language: str | None = None) -> str:
        """Delegates to the standalone response generator for reuse and testing."""
        return generate_response(intent, data, language=language or self.current_language)

    def fetch_intent_data(self, user_id: int, intent: str, *, language: str | None = None) -> Dict[str, Any]:
        """
        Fetches intent-specific prediction and timeline context from existing services.

        Returns a structure like:
        {
            "intent": "career",
            "prediction_summary": "...",
            "confidence": "high",
            "timeline_hint": "...",
            "matching_periods": [...]
        }
        """
        if self.horoscope_service is None:
            raise ValueError("Horoscope service dependency is required for data fetching.")

        active_language = _normalize_language(language or self.current_language)
        normalized_intent = str(intent or "general").strip().lower() or "general"
        logger.info("Fetching chat intent data for user_id=%s intent=%s.", user_id, normalized_intent)
        _, scored_predictions = self.horoscope_service.load_chart_for_user(user_id)
        try:
            timeline_payload = self.horoscope_service.get_timeline_data(user_id, language=active_language)
        except TypeError:
            timeline_payload = self.horoscope_service.get_timeline_data(user_id)

        if normalized_intent == "general":
            return self._build_general_data(
                scored_predictions=scored_predictions,
                timeline_rows=timeline_payload.get("timeline", []),
                language=active_language,
            )

        prediction_data = scored_predictions.get(normalized_intent, {})
        matching_periods = self._extract_matching_periods(
            timeline_payload.get("timeline", []),
            normalized_intent,
        )

        timeline_hint = self._build_timeline_hint(matching_periods, normalized_intent, language=active_language)

        return {
            "intent": normalized_intent,
            "prediction_summary": prediction_data.get("summary", ""),
            "confidence": prediction_data.get("confidence", "low"),
            "timeline_hint": timeline_hint,
            "matching_periods": matching_periods,
            "prediction_scores": scored_predictions,
        }

    def fetch_multi_intent_data(
        self,
        user_id: int,
        intents: list[str],
        *,
        language: str | None = None,
    ) -> Dict[str, Any]:
        """Fetches and aggregates multiple intent payloads for a combined chat answer."""
        active_language = _normalize_language(language or self.current_language)
        normalized_intents = [
            str(intent or "general").strip().lower()
            for intent in intents
            if str(intent or "").strip()
        ] or ["general"]

        sections = [self.fetch_intent_data(user_id, intent, language=active_language) for intent in normalized_intents]
        primary_section = sections[0]
        return {
            "intent": primary_section.get("intent", normalized_intents[0]),
            "intents": normalized_intents,
            "intent_sections": sections,
            "prediction_summary": primary_section.get("prediction_summary", ""),
            "confidence": primary_section.get("confidence", "low"),
            "timeline_hint": primary_section.get("timeline_hint", ""),
            "matching_periods": primary_section.get("matching_periods", []),
            "prediction_scores": primary_section.get("prediction_scores", {}),
        }

    def analyze_query(self, query: str, user_id: Optional[int] = None, *, language: str | None = None) -> Dict[str, Any]:
        """
        Returns basic structured analysis for a user question.

        When a user_id is provided, the result also includes intent-specific
        horoscope context fetched from the existing service layer.
        """
        normalized_query = str(query or "").strip()
        active_language = _normalize_language(language or self.current_language)
        conversation_memory = self.get_recent_queries(user_id) if user_id is not None else []
        detected_intents = self.detect_intents(normalized_query)
        detected_intent = detected_intents[0] if detected_intents else "general"
        resolved_intents = self._resolve_intents_with_memory(
            normalized_query,
            detected_intents,
            conversation_memory,
        )
        resolved_intent = resolved_intents[0] if resolved_intents else "general"
        logger.info(
            "Chat query analyzed for user_id=%s detected_intents=%s resolved_intents=%s.",
            user_id,
            detected_intents,
            resolved_intents,
        )
        result: Dict[str, Any] = {
            "query": normalized_query,
            "intent": resolved_intent,
            "detected_intent": detected_intent,
            "detected_intents": detected_intents,
            "intents": resolved_intents,
            "recent_queries": conversation_memory,
        }
        if user_id is not None:
            if len(resolved_intents) > 1:
                result["data"] = self.fetch_multi_intent_data(user_id, resolved_intents, language=active_language)
            else:
                result["data"] = self.fetch_intent_data(user_id, result["intent"], language=active_language)
            unified_predictions = self._get_unified_predictions(user_id, language=active_language)
            result["data"]["unified_predictions"] = unified_predictions
            unified_dasha_timeline = self._get_unified_dasha_timeline(user_id, language=active_language)
            result["data"]["timeline_forecast"] = self._get_cached_timeline_forecast(
                user_id=user_id,
                predictions=unified_predictions,
                dasha_timeline=unified_dasha_timeline,
                language=active_language,
            )
            result["data"]["reasoning"] = self.reasoning_service.generate_explanations(
                unified_predictions,
                user_question=normalized_query,
                language=active_language,
            )
            intent_sections = result["data"].get("intent_sections")
            if isinstance(intent_sections, list):
                for section in intent_sections:
                    if not isinstance(section, dict):
                        continue
                    section_intent = str(section.get("intent", "general")).strip().lower() or "general"
                    section["reasoning"] = self.reasoning_service.generate_explanations(
                        unified_predictions,
                        user_question=section_intent,
                        language=active_language,
                    )
            result["data"]["memory_note"] = self._build_memory_note(
                normalized_query,
                resolved_intents,
                conversation_memory,
                language=active_language,
            )
        return result

    def _get_cached_timeline_forecast(
        self,
        *,
        user_id: int,
        predictions: list[dict[str, Any]],
        dasha_timeline: list[dict[str, Any]],
        language: str = "en",
    ) -> dict[str, Any]:
        """Returns cached timeline forecast for chat flows, computing it only once per user/TTL."""
        cached = self.cache.get("chat_timeline_forecast", user_id)
        if isinstance(cached, dict):
            cached_language = str(cached.get("_language", "en")).strip().lower() or "en"
            if cached_language == language:
                return cached
        forecast = self.timeline_service.build_timeline_forecast(
            predictions,
            dasha_timeline,
            language=language,
        )
        if isinstance(forecast, dict):
            forecast["_language"] = language
        self.cache.set("chat_timeline_forecast", user_id, forecast)
        return forecast

    def ask(self, user_id: int, query: str, *, language: str | None = None) -> Dict[str, Any]:
        """
        Runs the end-to-end horoscope chat flow for a single user question.

        Returns:
        {
            "query": "...",
            "intent": "...",
            "data": {...},
            "response": "..."
        }
        """
        active_language = _normalize_language(language or self.current_language)
        log_user_action("chat_query", user_id=user_id, query=query)
        analysis = self.analyze_query(query, user_id=user_id, language=active_language)

        used_event_service = False
        resolved_intents = analysis.get("intents", [])
        use_event_service = self.event_service.is_specific_query(query) and len(resolved_intents) == 1
        if use_event_service:
            event_result = self.event_service.predict_event(
                user_query=query,
                predictions=analysis.get("data", {}).get("unified_predictions", []),
                timeline_data=analysis.get("data", {}).get("timeline_forecast", {}),
                reasoning_data=analysis.get("data", {}).get("reasoning", []),
                language=active_language,
            )
            analysis["event_prediction"] = event_result
            if str(event_result.get("answer", "")).strip():
                analysis["response"] = str(event_result.get("answer", "")).strip()
                analysis["response_source"] = "event_service"
                used_event_service = True

        if not used_event_service:
            local_response = self.generate_response(
                analysis["intent"],
                analysis.get("data", {}),
                language=active_language,
            )
            analysis["response"] = local_response
            analysis["response_source"] = "local"

        if self.ai_refiner is not None:
            try:
                if self.ai_refiner.is_enabled():
                    analysis["response"] = self.ai_refiner.refine_response(
                        query,
                        analysis,
                        language=active_language,
                    )
                    analysis["response_source"] = "openai"
            except Exception as exc:
                logger.warning("AI refinement failed, falling back to local response: %s", exc)
                analysis["ai_error"] = str(exc)

        self._remember_interaction(user_id, analysis)
        logger.info("Chat response generated for user_id=%s source=%s.", user_id, analysis["response_source"])
        return analysis

    def get_recent_queries(self, user_id: Optional[int]) -> list[dict]:
        """Returns the last five chat exchanges for a user."""
        if user_id is None:
            return []
        return list(self.memory.get(user_id, []))

    def _extract_matching_periods(self, timeline_rows: list[dict], intent: str) -> list[dict]:
        """Filters the unified timeline down to periods relevant to the requested intent."""
        matching_periods = []
        for row in timeline_rows:
            events = row.get("events", [])
            matched_events = [
                event
                for event in events
                if str(event.get("type", "general")).strip().lower() == intent
            ]
            if matched_events:
                matching_periods.append(
                    {
                        "planet": row.get("planet", "Unknown"),
                        "start": row.get("start", ""),
                        "end": row.get("end", ""),
                        "events": matched_events,
                    }
                )
        return matching_periods

    def _resolve_intents_with_memory(
        self,
        query: str,
        detected_intents: list[str],
        recent_queries: list[dict],
    ) -> list[str]:
        """Uses recent conversation context to resolve ambiguous follow-up questions."""
        normalized_detected = [
            str(intent or "general").strip().lower()
            for intent in detected_intents
            if str(intent or "").strip()
        ] or ["general"]

        if normalized_detected != ["general"]:
            return normalized_detected
        if not recent_queries or not self._is_follow_up_query(query):
            return normalized_detected

        last_intents = recent_queries[-1].get("intents") or [recent_queries[-1].get("intent", "general")]
        resolved = [
            str(intent or "general").strip().lower()
            for intent in last_intents
            if str(intent or "").strip()
        ]
        return resolved or ["general"]

    def _is_follow_up_query(self, query: str) -> bool:
        """Detects short follow-up style questions that likely depend on prior context."""
        tokens = re.findall(r"[a-z]+", str(query or "").lower())
        if not tokens:
            return False
        if len(tokens) <= 4 and any(token in FOLLOW_UP_MARKERS for token in tokens):
            return True
        normalized = " ".join(tokens)
        return normalized.startswith(("what about", "how about", "and ", "also "))


    def _build_memory_note(
        self,
        query: str,
        intents: list[str],
        recent_queries: list[dict],
        *,
        language: str = "en",
    ) -> str:
        """Adds a light conversational bridge when the answer uses follow-up context."""
        if not recent_queries:
            return ""
        if not self._is_follow_up_query(query):
            return ""

        previous_intents = recent_queries[-1].get("intents") or [recent_queries[-1].get("intent", "general")]
        previous_label = self._format_intent_labels(previous_intents)
        current_label = self._format_intent_labels(intents)
        active_language = _normalize_language(language)
        if active_language == "hi":
            if previous_label == current_label:
                return f"यह आपके पिछले {current_label} प्रश्न का ही विस्तार है।"
            return f"यह आपके पिछले {previous_label} प्रश्न से जुड़ा है, अब फोकस {current_label} पर है।"
        if active_language == "or":
            if previous_label == current_label:
                return f"ଏହା ଆପଣଙ୍କ ପୂର୍ବରୁ ଥିବା {current_label} ପ୍ରଶ୍ନର ଅନୁସରଣ।"
            return f"ଏହା ଆପଣଙ୍କ ପୂର୍ବରୁ ଥିବା {previous_label} ପ୍ରଶ୍ନକୁ ଅନୁସରଣ କରି, ଏବେ {current_label} ଉପରେ କେନ୍ଦ୍ରିତ।"
        if previous_label == current_label:
            return f"This follows your earlier {current_label} question."
        return f"This follows your earlier {previous_label} question, now focusing on {current_label}."

    def _format_intent_labels(self, intents: list[str]) -> str:
        """Formats one or more intents for natural language notes."""
        labels = [
            str(intent or "general").strip().lower()
            for intent in intents
            if str(intent or "").strip()
        ] or ["general"]
        if len(labels) == 1:
            return labels[0]
        if len(labels) == 2:
            return f"{labels[0]} and {labels[1]}"
        return ", ".join(labels[:-1]) + f", and {labels[-1]}"

    def _remember_interaction(self, user_id: int, analysis: Dict[str, Any]) -> None:
        """Stores the last five user queries and answers for lightweight follow-up context."""
        self.last_query_by_user[user_id] = analysis.get("query", "")
        self.memory[user_id].append(
            {
                "query": analysis.get("query", ""),
                "intent": analysis.get("intent", "general"),
                "intents": analysis.get("intents", [analysis.get("intent", "general")]),
                "response": analysis.get("response", ""),
                "response_source": analysis.get("response_source", "local"),
            }
        )

    def _build_general_data(
        self,
        scored_predictions: Dict[str, Dict[str, Any]],
        timeline_rows: list[dict],
        *,
        language: str = "en",
    ) -> Dict[str, Any]:
        """Builds a fallback context when the query intent is general or unclear."""
        filtered_predictions = {
            category: details
            for category, details in scored_predictions.items()
            if category != "system"
        }
        if not filtered_predictions:
            return {
                "intent": "general",
                "prediction_summary": "",
                "confidence": "low",
                "timeline_hint": "",
                "matching_periods": [],
                "prediction_scores": scored_predictions,
            }

        top_category, top_details = max(
            filtered_predictions.items(),
            key=lambda item: float(item[1].get("score", 0.0)),
        )
        matching_periods = self._extract_matching_periods(timeline_rows, top_category)
        timeline_hint = self._build_timeline_hint(matching_periods, top_category, language=language)

        return {
            "intent": "general",
            "prediction_summary": top_details.get("summary", ""),
            "confidence": top_details.get("confidence", "low"),
            "timeline_hint": timeline_hint,
            "matching_periods": matching_periods,
            "prediction_scores": scored_predictions,
            "top_category": top_category,
        }

    def _build_timeline_hint(self, matching_periods: list[dict], intent: str, *, language: str = "en") -> str:
        """Builds a concise timeline hint from the earliest relevant dasha period."""
        if not matching_periods:
            return ""

        first_period = matching_periods[0]
        first_event = first_period.get("events", [{}])[0]
        summary = _clean_sentence(first_event.get("summary", ""))
        start_year = str(first_period.get("start", ""))[:4]
        end_year = str(first_period.get("end", ""))[:4]
        planet = first_period.get("planet", "this")
        active_language = _normalize_language(language)
        if active_language == "hi":
            base_hint = (
                f"{intent.title()} विषय {planet} महादशा में {start_year} से {end_year} के बीच अधिक सक्रिय हैं"
            )
        elif active_language == "or":
            base_hint = (
                f"{intent.title()} ବିଷୟ {planet} ମହାଦଶା ସମୟରେ {start_year} ରୁ {end_year} ମଧ୍ୟରେ ଅଧିକ ସକ୍ରିୟ"
            )
        else:
            base_hint = (
                f"{intent.title()} themes are highlighted during {planet} Mahadasha "
                f"between {start_year} and {end_year}"
            )
        if summary:
            return f"{base_hint}. {summary}"
        return base_hint + "."

    def _get_unified_predictions(self, user_id: int, *, language: str | None = None) -> list[dict]:
        """Loads unified-engine prediction rows for reasoning/event generation."""
        active_language = _normalize_language(language or self.current_language)
        advanced_data = self._get_advanced_data_payload(user_id, language=active_language)
        unified_payload = advanced_data.get("unified", {}) if isinstance(advanced_data, dict) else {}
        predictions = unified_payload.get("predictions", []) if isinstance(unified_payload, dict) else []
        if not isinstance(predictions, list):
            return []
        return [dict(item) for item in predictions if isinstance(item, dict)]

    def _get_unified_dasha_timeline(self, user_id: int, *, language: str | None = None) -> list[dict]:
        """Loads dasha timeline rows used for timeline-event mapping."""
        active_language = _normalize_language(language or self.current_language)
        advanced_data = self._get_advanced_data_payload(user_id, language=active_language)
        dasha_timeline = advanced_data.get("dasha", []) if isinstance(advanced_data, dict) else []
        if not isinstance(dasha_timeline, list):
            return []
        return [dict(item) for item in dasha_timeline if isinstance(item, dict)]

    def _get_advanced_data_payload(self, user_id: int, *, language: str = "en") -> dict[str, Any]:
        """
        Loads advanced service payload once and returns a stable dict.

        Returns {} when dependencies/data are unavailable.
        """
        cached_payload = self.cache.get("chat_advanced_data", user_id)
        if isinstance(cached_payload, dict):
            cached_language = str(cached_payload.get("_language", "en")).strip().lower() or "en"
            if cached_language == language:
                return cached_payload

        if self.horoscope_service is None:
            return {}

        try:
            user_repo = getattr(self.horoscope_service, "user_repo", None)
            chart_repo = getattr(self.horoscope_service, "chart_repo", None)
            if user_repo is None or chart_repo is None:
                return {}

            user = user_repo.get_by_id(user_id)
            if not user:
                return {}

            chart_data_models = chart_repo.get_by_user_id(user_id)
            if not chart_data_models:
                return {}

            from app.services.astrology_advanced_service import AstrologyAdvancedService

            advanced_service = AstrologyAdvancedService()
            advanced_data = advanced_service.generate_advanced_data(
                chart_data_models,
                str(user.dob),
                language=language,
            )
            payload = advanced_data if isinstance(advanced_data, dict) else {}
            self.cache.set("chat_advanced_data", user_id, payload)
            return payload
        except Exception as exc:
            logger.warning("Advanced payload fetch for reasoning/event failed: %s", exc)
            return {}
