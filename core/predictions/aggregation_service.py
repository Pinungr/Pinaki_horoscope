from __future__ import annotations

import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Mapping

from .prediction_service import get_prediction, get_prediction_weight


EXPLANATION_TEMPLATES = {
    "en": "Due to {rule}.",
    "hi": "{rule} के कारण।",
    "or": "{rule} କାରଣରୁ।",
}


def aggregate_predictions(rule_keys: Iterable[Any], language: str | None = None) -> dict[str, Any]:
    normalized_language = str(language or "en").strip().lower() or "en"
    unique_keys = _sort_by_weight(_deduplicate_keys(rule_keys))

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


def aggregate_context_predictions(predictions: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [dict(item) for item in (predictions or []) if isinstance(item, Mapping)]
    sorted_rows = sorted(rows, key=lambda item: _safe_score(item.get("score")), reverse=True)
    top = sorted_rows[:5]

    top_areas: list[str] = []
    for item in top[:3]:
        area = str(item.get("area", "")).strip().lower()
        if area and area not in top_areas:
            top_areas.append(area)

    time_focus: list[str] = []
    for item in top:
        timing = item.get("timing")
        if not isinstance(timing, Mapping):
            continue
        if str(timing.get("relevance", "")).strip().lower() != "high":
            continue
        area = str(item.get("area", "")).strip().lower()
        if area and area not in time_focus:
            time_focus.append(area)

    confidence_score = 0
    if top:
        confidence_score = int(
            round(sum(_safe_score(item.get("score")) for item in top) / len(top))
        )

    strong_yogas = sum(1 for item in rows if str(item.get("strength", "")).strip().lower() == "strong")
    meta = {
        "total_yogas": len(rows),
        "strong_yogas": strong_yogas,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "summary": {
            "top_areas": top_areas,
            "confidence_score": confidence_score,
            "time_focus": time_focus[:3],
        },
        "predictions": top,
        "meta": meta,
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


def _sort_by_weight(rule_keys: list[str]) -> list[str]:
    return sorted(
        rule_keys,
        key=lambda key: get_prediction_weight(key),
        reverse=True,
    )


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


def _safe_score(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
