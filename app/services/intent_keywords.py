# -*- coding: utf-8 -*-
"""
app/services/intent_keywords.py
================================
Single source of truth for Vedic horoscope intent detection.

Both HoroscopeChatService and EventService import from here so that
keyword additions/changes are reflected consistently across the
whole chat + event pipeline.
"""
from __future__ import annotations

import re
from typing import Dict, Iterable


# ---------------------------------------------------------------------------
# Canonical keyword map
# ---------------------------------------------------------------------------

INTENT_KEYWORDS: Dict[str, tuple[str, ...]] = {
    "career": (
        "job", "career", "work", "promotion", "profession", "office", "business",
        "employment", "employer", "boss", "role", "success", "successes",
        "jobs", "careers", "promotions",
    ),
    "marriage": (
        "marriage", "wedding", "love", "relationship", "relationships", "partner",
        "spouse", "romance", "romantic", "husband", "wife", "commitment",
        "married",
    ),
    "finance": (
        "money", "finance", "financial", "income", "salary", "earnings", "wealth",
        "investment", "investments", "cash", "assets", "loan", "loans", "debt",
        "profit", "profits", "savings", "finances", "earn",
    ),
    "health": (
        "health", "healthy", "wellness", "fitness", "disease", "healing", "recovery",
    ),
}

# Normalisation aliases — any area value that should be treated as another
AREA_ALIASES: Dict[str, str] = {
    "wealth": "finance",
    "financial": "finance",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tokenize(query: str) -> list[str]:
    """Splits a query into lowercase alpha tokens."""
    return re.findall(r"[a-z]+", str(query or "").lower())


def _count_matches(tokens: list[str], keywords: Iterable[str]) -> int:
    token_set = set(tokens)
    return sum(1 for kw in keywords if kw in token_set)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_intent(query: str) -> str:
    """
    Returns the single most likely intent for *query*, or ``"general"`` when
    no intent keyword is found.

    Possible values: ``"career"``, ``"marriage"``, ``"finance"``,
    ``"health"``, ``"general"``.
    """
    tokens = _tokenize(query)
    if not tokens:
        return "general"
    scores = {
        intent: _count_matches(tokens, keywords)
        for intent, keywords in INTENT_KEYWORDS.items()
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"


def detect_intents(query: str) -> list[str]:
    """
    Returns one or more intents ordered strongest-first.
    Falls back to ``["general"]``.

    A secondary intent is included when its score is within 1 hit of the
    top score (so "job and money?" → ["career", "finance"]).
    """
    tokens = _tokenize(query)
    if not tokens:
        return ["general"]

    scores = {
        intent: _count_matches(tokens, keywords)
        for intent, keywords in INTENT_KEYWORDS.items()
    }

    positive = [
        intent
        for intent, score in sorted(scores.items(), key=lambda i: i[1], reverse=True)
        if score > 0
    ]

    if not positive:
        return ["general"]

    top_score = scores[positive[0]]
    selected = [i for i in positive if scores[i] >= max(1, top_score - 1)]
    return selected or ["general"]


def normalize_area(area: str) -> str:
    """Maps area aliases to their canonical value (e.g. "wealth" → "finance")."""
    normalized = str(area or "general").strip().lower() or "general"
    return AREA_ALIASES.get(normalized, normalized)
