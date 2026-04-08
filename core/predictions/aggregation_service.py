from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List

from .prediction_service import get_prediction


EXPLANATION_TEMPLATES = {
    "en": "Due to {rule}.",
    "hi": "{rule} के कारण।",
    "or": "{rule} କାରଣରୁ।",
}


def aggregate_predictions(rule_keys: Iterable[Any], language: str | None = None) -> dict[str, Any]:
    normalized_language = str(language or "en").strip().lower() or "en"
    unique_keys = _deduplicate_keys(rule_keys)

    details: list[dict[str, str]] = []
    seen_texts: list[str] = []
    summary_parts: list[str] = []

    for rule_key in unique_keys:
        text = get_prediction(rule_key, normalized_language)
        if not text:
            continue

        explanation = _build_explanation(rule_key, normalized_language)
        details.append(
            {
                "rule": rule_key,
                "text": text,
                "explanation": explanation,
            }
        )

        if not _contains_similar_text(seen_texts, text):
            seen_texts.append(text)
            summary_parts.append(text)

    return {
        "summary": " ".join(summary_parts).strip(),
        "details": details,
    }


def _deduplicate_keys(rule_keys: Iterable[Any]) -> list[str]:
    unique_keys: list[str] = []
    seen: set[str] = set()

    for rule_key in rule_keys or []:
        normalized_key = str(rule_key or "").strip()
        if not normalized_key or normalized_key in seen:
            continue
        seen.add(normalized_key)
        unique_keys.append(normalized_key)

    return unique_keys


def _build_explanation(rule_key: str, language: str) -> str:
    template = EXPLANATION_TEMPLATES.get(language, EXPLANATION_TEMPLATES["en"])
    return template.format(rule=_humanize_rule_key(rule_key))


def _humanize_rule_key(rule_key: str) -> str:
    words = re.sub(r"[_\s]+", " ", str(rule_key or "").strip()).split()
    return " ".join(word.capitalize() for word in words)


def _contains_similar_text(existing_texts: List[str], candidate: str) -> bool:
    candidate_key = _normalize_text(candidate)
    if not candidate_key:
        return False

    for existing_text in existing_texts:
        existing_key = _normalize_text(existing_text)
        if not existing_key:
            continue
        if existing_key == candidate_key:
            return True
        if existing_key in candidate_key or candidate_key in existing_key:
            return True
        if SequenceMatcher(None, existing_key, candidate_key).ratio() >= 0.85:
            return True

    return False


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", str(text or "").lower())).strip()
