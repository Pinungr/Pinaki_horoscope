import re
from difflib import SequenceMatcher
from typing import List, Dict, Set, Any
from app.models.domain import Rule

class InterpreterEngine:
    """Combines rules, avoids duplicates, and scores predictions."""

    def interpret(self, raw_predictions: List[Any], all_rules: List[Rule]) -> List[Dict[str, str]]:
        """
        Takes raw string predictions from RuleEngine and cross-references them against all_rules 
        to recover Categories and Priorities dynamically without breaking Phase 1.
        """
        seen_texts: Set[str] = set()
        interpretations = []

        # Build a lookup table from all_rules
        rule_lookup = {}
        for r in all_rules:
            norm_txt = r.result_text.strip().lower()
            if norm_txt not in rule_lookup:
                rule_lookup[norm_txt] = r

        for raw_prediction in raw_predictions:
            raw_text = str(
                raw_prediction.get("text")
                if isinstance(raw_prediction, dict)
                else raw_prediction
            ).strip()
            normalized_text = raw_text.strip().lower()
            
            # Avoid exact duplicates
            if normalized_text in seen_texts:
                continue
            seen_texts.add(normalized_text)
            
            # Lookup metadata
            matched_rule = rule_lookup.get(normalized_text)
            score = matched_rule.priority if matched_rule else 0
            cat = matched_rule.category.strip() if matched_rule and matched_rule.category else "General"
            
            interpretations.append({
                "text": raw_text,
                "category": cat,
                "score": score
            })

        # Sort by priority descending (highest score first)
        sorted_interpretations = sorted(interpretations, key=lambda i: i["score"], reverse=True)

        return sorted_interpretations

    def refine_scored_predictions(self, scored_predictions: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Enhances scored prediction payloads with cleaner, less repetitive summaries.

        The return shape stays backward compatible with the existing service/UI flow:
        each category remains a dictionary and still exposes ``summary``.
        """
        refined: Dict[str, Dict[str, Any]] = {}
        for category, details in (scored_predictions or {}).items():
            details_copy = dict(details or {})
            raw_summary = str(details_copy.get("summary", "") or "").strip()
            refined_summary = self._build_narrative_summary(
                category=str(category or "general"),
                raw_summary=raw_summary,
                effect=str(details_copy.get("effect", "neutral") or "neutral"),
                confidence=str(details_copy.get("confidence", "low") or "low"),
            )

            details_copy["raw_summary"] = raw_summary
            details_copy["summary"] = refined_summary
            refined[category] = details_copy

        return refined

    def _build_narrative_summary(
        self,
        *,
        category: str,
        raw_summary: str,
        effect: str,
        confidence: str,
    ) -> str:
        """Builds a readable narrative sentence while removing duplicate phrasing."""
        clean_sentences = self._collapse_similar_sentences(self._split_sentences(raw_summary))
        detail_text = " ".join(clean_sentences).strip()
        lead = self._lead_phrase(category=category, effect=effect, confidence=confidence, has_detail=bool(detail_text))

        if not detail_text:
            return lead

        if self._is_similar_sentence(lead, detail_text):
            return detail_text

        return f"{lead} {detail_text}".strip()

    def _lead_phrase(self, *, category: str, effect: str, confidence: str, has_detail: bool) -> str:
        """Creates a category-aware lead sentence for the interpreted summary."""
        subject = self._category_subject(category)
        normalized_effect = (effect or "neutral").strip().lower()
        normalized_confidence = (confidence or "low").strip().lower()

        if normalized_effect == "positive":
            if normalized_confidence == "high":
                return f"{subject} look strongly supportive."
            if normalized_confidence == "medium":
                return f"{subject} look reasonably supportive."
            return f"{subject} show some support, though the signal is still modest."

        if normalized_effect == "negative":
            if normalized_confidence == "high":
                return f"{subject} show notable pressure and may need extra care."
            if normalized_confidence == "medium":
                return f"{subject} show some pressure and may need careful handling."
            return f"{subject} show mild pressure, though the indication is still limited."

        if has_detail:
            return f"{subject} show a mixed picture."
        return f"{subject} remain balanced overall."

    def _category_subject(self, category: str) -> str:
        """Maps internal categories into human-friendly narrative subjects."""
        normalized = str(category or "general").strip().lower()
        if normalized == "career":
            return "Career prospects"
        if normalized == "marriage":
            return "Relationship and marriage prospects"
        if normalized == "finance":
            return "Financial prospects"
        return "Overall indications"

    def _split_sentences(self, text: str) -> List[str]:
        """Splits text into sentence-like fragments."""
        cleaned = " ".join(str(text or "").split()).strip()
        if not cleaned:
            return []

        parts = re.split(r"(?<=[.!?])\s+", cleaned)
        return [part.strip() for part in parts if part.strip()]

    def _collapse_similar_sentences(self, sentences: List[str]) -> List[str]:
        """Removes exact and near-duplicate phrasing while preserving order."""
        unique_sentences: List[str] = []
        for sentence in sentences:
            if any(self._is_similar_sentence(sentence, existing) for existing in unique_sentences):
                continue
            unique_sentences.append(sentence)
        return unique_sentences

    def _is_similar_sentence(self, first: str, second: str) -> bool:
        """Checks whether two sentences are similar enough to collapse."""
        first_key = self._normalize_sentence(first)
        second_key = self._normalize_sentence(second)
        if not first_key or not second_key:
            return False
            
        # Yoga-aware protection: handles lowercase and boundary variations
        yoga_regex = r"\b(\w+)\s+[Yy]oga\b"
        yogas_in_first = {m.group(1).lower() for m in re.finditer(yoga_regex, first)}
        yogas_in_second = {m.group(1).lower() for m in re.finditer(yoga_regex, second)}
        
        if yogas_in_first != yogas_in_second:
            return False

        if first_key == second_key:
            return True
        if first_key in second_key or second_key in first_key:
            return True
            
        similarity_threshold = 0.8
        if yogas_in_first and yogas_in_first == yogas_in_second:
            similarity_threshold = 0.6
            
        return SequenceMatcher(None, first_key, second_key).ratio() >= similarity_threshold

    def _normalize_sentence(self, sentence: str) -> str:
        """Normalizes a sentence for duplicate detection."""
        return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", str(sentence or "").lower())).strip()
