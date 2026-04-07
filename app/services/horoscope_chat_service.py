from __future__ import annotations

from collections import defaultdict, deque
import re
import logging
from typing import Any, Dict, Iterable, Optional
from app.utils.logger import log_user_action


INTENT_KEYWORDS: Dict[str, tuple[str, ...]] = {
    "career": (
        "job", "career", "work", "promotion", "profession", "office", "business",
        "employment", "employer", "boss", "role", "success", "successes",
        "jobs", "careers", "promotions",
    ),
    "marriage": (
        "marriage", "wedding", "love", "relationship", "relationships", "partner",
        "spouse", "romance", "romantic", "husband", "wife", "commitment",
    ),
    "finance": (
        "money", "finance", "financial", "income", "salary", "earnings", "wealth",
        "investment", "investments", "cash", "assets", "loan", "loans", "debt",
        "profit", "profits", "savings", "finances",
    ),
}

logger = logging.getLogger(__name__)
FOLLOW_UP_MARKERS = {
    "and",
    "also",
    "then",
    "next",
    "what",
    "about",
    "how",
    "more",
}


def _tokenize_query(query: str) -> list[str]:
    """Splits a user query into normalized keyword-friendly tokens."""
    return re.findall(r"[a-z]+", str(query or "").lower())


def detect_intent(query: str) -> str:
    """
    Detects the most likely horoscope intent from a natural-language question.

    Returns one of:
    - career
    - marriage
    - finance
    - general
    """
    tokens = _tokenize_query(query)
    if not tokens:
        return "general"

    scores = {
        intent: _count_matches(tokens, keywords)
        for intent, keywords in INTENT_KEYWORDS.items()
    }

    best_intent = max(scores, key=scores.get)
    return best_intent if scores[best_intent] > 0 else "general"


def detect_intents(query: str) -> list[str]:
    """
    Detects one or more likely intents from a natural-language question.

    Returns intents ordered by strongest signal first. Falls back to ``["general"]``.
    """
    tokens = _tokenize_query(query)
    if not tokens:
        return ["general"]

    scores = {
        intent: _count_matches(tokens, keywords)
        for intent, keywords in INTENT_KEYWORDS.items()
    }

    positive_hits = [
        intent
        for intent, score in sorted(scores.items(), key=lambda item: item[1], reverse=True)
        if score > 0
    ]

    if not positive_hits:
        return ["general"]

    top_score = scores[positive_hits[0]]
    selected = [intent for intent in positive_hits if scores[intent] >= max(1, top_score - 1)]
    return selected or ["general"]


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


def _confidence_phrase(confidence: str) -> str:
    """Maps confidence values into human-friendly language."""
    normalized = str(confidence or "").strip().lower()
    if normalized == "high":
        return "The indications are strong."
    if normalized == "medium":
        return "The indications are reasonably supportive."
    if normalized == "low":
        return "The indications are present but still modest."
    return "The indications are mixed."


def generate_response(intent: str, data: Dict[str, Any]) -> str:
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
        return _generate_multi_intent_response(intent_sections, data)

    normalized_intent = str(intent or "general").strip().lower() or "general"
    prediction_summary = _clean_sentence(data.get("prediction_summary", ""))
    timeline_hint = _clean_sentence(data.get("timeline_hint", ""))
    confidence_text = _confidence_phrase(data.get("confidence", ""))
    memory_note = _clean_sentence(data.get("memory_note", ""))

    opener_map = {
        "career": "Your career outlook suggests the following:",
        "marriage": "Your relationship and marriage outlook suggests the following:",
        "finance": "Your financial outlook suggests the following:",
        "general": "Here is the astrological view based on your question:",
    }
    opener = opener_map.get(normalized_intent, opener_map["general"])

    parts = [opener]
    if prediction_summary:
        parts.append(prediction_summary)
    parts.append(confidence_text)
    if memory_note:
        parts.append(memory_note)
    if timeline_hint:
        parts.append(f"Timeline hint: {timeline_hint}")

    if len(parts) == 2 and not prediction_summary and not timeline_hint:
        parts.append("There is not enough structured astrological context yet for a specific answer.")

    return " ".join(parts)


def _generate_multi_intent_response(intent_sections: list[dict], data: Dict[str, Any]) -> str:
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
                    "memory_note": "",
                },
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

    def __init__(self, horoscope_service: Optional[object] = None, ai_refiner: Optional[object] = None):
        self.horoscope_service = horoscope_service
        self.ai_refiner = ai_refiner
        self.memory: dict[int, deque[dict[str, Any]]] = defaultdict(lambda: deque(maxlen=5))
        self.last_query_by_user: dict[int, str] = {}

    def detect_intent(self, query: str) -> str:
        """Delegates to the standalone intent detector for reuse and testing."""
        return detect_intent(query)

    def detect_intents(self, query: str) -> list[str]:
        """Delegates to the standalone multi-intent detector for reuse and testing."""
        return detect_intents(query)

    def generate_response(self, intent: str, data: Dict[str, Any]) -> str:
        """Delegates to the standalone response generator for reuse and testing."""
        return generate_response(intent, data)

    def fetch_intent_data(self, user_id: int, intent: str) -> Dict[str, Any]:
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

        normalized_intent = str(intent or "general").strip().lower() or "general"
        logger.info("Fetching chat intent data for user_id=%s intent=%s.", user_id, normalized_intent)
        _, scored_predictions = self.horoscope_service.load_chart_for_user(user_id)
        timeline_payload = self.horoscope_service.get_timeline_data(user_id)

        if normalized_intent == "general":
            return self._build_general_data(
                scored_predictions=scored_predictions,
                timeline_rows=timeline_payload.get("timeline", []),
            )

        prediction_data = scored_predictions.get(normalized_intent, {})
        matching_periods = self._extract_matching_periods(
            timeline_payload.get("timeline", []),
            normalized_intent,
        )

        timeline_hint = self._build_timeline_hint(matching_periods, normalized_intent)

        return {
            "intent": normalized_intent,
            "prediction_summary": prediction_data.get("summary", ""),
            "confidence": prediction_data.get("confidence", "low"),
            "timeline_hint": timeline_hint,
            "matching_periods": matching_periods,
            "prediction_scores": scored_predictions,
        }

    def fetch_multi_intent_data(self, user_id: int, intents: list[str]) -> Dict[str, Any]:
        """Fetches and aggregates multiple intent payloads for a combined chat answer."""
        normalized_intents = [
            str(intent or "general").strip().lower()
            for intent in intents
            if str(intent or "").strip()
        ] or ["general"]

        sections = [self.fetch_intent_data(user_id, intent) for intent in normalized_intents]
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

    def analyze_query(self, query: str, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Returns basic structured analysis for a user question.

        When a user_id is provided, the result also includes intent-specific
        horoscope context fetched from the existing service layer.
        """
        normalized_query = str(query or "").strip()
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
                result["data"] = self.fetch_multi_intent_data(user_id, resolved_intents)
            else:
                result["data"] = self.fetch_intent_data(user_id, result["intent"])
            result["data"]["memory_note"] = self._build_memory_note(
                normalized_query,
                resolved_intents,
                conversation_memory,
            )
        return result

    def ask(self, user_id: int, query: str) -> Dict[str, Any]:
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
        log_user_action("chat_query", user_id=user_id, query=query)
        analysis = self.analyze_query(query, user_id=user_id)
        local_response = self.generate_response(
            analysis["intent"],
            analysis.get("data", {}),
        )
        analysis["response"] = local_response
        analysis["response_source"] = "local"

        if self.ai_refiner is not None:
            try:
                if self.ai_refiner.is_enabled():
                    analysis["response"] = self.ai_refiner.refine_response(query, analysis)
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
        tokens = _tokenize_query(query)
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
    ) -> str:
        """Adds a light conversational bridge when the answer uses follow-up context."""
        if not recent_queries:
            return ""
        if not self._is_follow_up_query(query):
            return ""

        previous_intents = recent_queries[-1].get("intents") or [recent_queries[-1].get("intent", "general")]
        previous_label = self._format_intent_labels(previous_intents)
        current_label = self._format_intent_labels(intents)
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
        timeline_hint = self._build_timeline_hint(matching_periods, top_category)

        return {
            "intent": "general",
            "prediction_summary": top_details.get("summary", ""),
            "confidence": top_details.get("confidence", "low"),
            "timeline_hint": timeline_hint,
            "matching_periods": matching_periods,
            "prediction_scores": scored_predictions,
            "top_category": top_category,
        }

    def _build_timeline_hint(self, matching_periods: list[dict], intent: str) -> str:
        """Builds a concise timeline hint from the earliest relevant dasha period."""
        if not matching_periods:
            return ""

        first_period = matching_periods[0]
        first_event = first_period.get("events", [{}])[0]
        summary = _clean_sentence(first_event.get("summary", ""))
        start_year = str(first_period.get("start", ""))[:4]
        end_year = str(first_period.get("end", ""))[:4]
        planet = first_period.get("planet", "this")

        base_hint = (
            f"{intent.title()} themes are highlighted during {planet} Mahadasha "
            f"between {start_year} and {end_year}"
        )
        if summary:
            return f"{base_hint}. {summary}"
        return base_hint + "."
