from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List

_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "will",
    "with",
}


def _normalize_prediction(prediction: Any) -> Dict[str, Any]:
    """
    Normalizes a raw prediction into a scorer-friendly dictionary.

    Supported inputs:
    - {"text": "...", "category": "...", "weight": 0.8}
    - {"result_text": "...", "category": "...", "weight": 0.8}
    - "Plain prediction text"
    """
    if isinstance(prediction, dict):
        text = str(
            prediction.get("text")
            or prediction.get("result_text")
            or prediction.get("summary")
            or ""
        ).strip()
        category = str(prediction.get("category") or "general").strip().lower()

        try:
            weight = float(prediction.get("weight", 1.0) or 1.0)
        except (TypeError, ValueError):
            weight = 1.0
    else:
        text = str(prediction).strip()
        category = "general"
        weight = 1.0

    return {
        "text": text,
        "category": category or "general",
        "weight": weight,
    }


def _split_sentences(text: str) -> List[str]:
    text = " ".join(text.split())
    if not text:
        return []

    parts: List[str] = []
    current = []
    for char in text:
        current.append(char)
        if char in ".!?;":
            sentence = "".join(current).strip()
            if sentence:
                parts.append(sentence)
            current = []

    trailing = "".join(current).strip()
    if trailing:
        parts.append(trailing)

    return parts


def _deduplicate_sentences(texts: Iterable[str]) -> List[str]:
    seen = set()
    unique_sentences: List[str] = []

    for text in texts:
        for sentence in _split_sentences(text):
            normalized = sentence.strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique_sentences.append(sentence)

    return unique_sentences


def _normalize_sentence_key(sentence: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", sentence.lower())).strip()


def _tokenize_sentence(sentence: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", sentence.lower())
        if token not in _STOP_WORDS
    }


def _sentences_are_similar(first: str, second: str) -> bool:
    first_key = _normalize_sentence_key(first)
    second_key = _normalize_sentence_key(second)

    if not first_key or not second_key:
        return False
    if first_key == second_key:
        return True
    if first_key in second_key or second_key in first_key:
        return True

    first_tokens = _tokenize_sentence(first)
    second_tokens = _tokenize_sentence(second)
    if first_tokens and second_tokens:
        shared_tokens = len(first_tokens & second_tokens)
        min_token_count = min(len(first_tokens), len(second_tokens))
        if min_token_count and (shared_tokens / min_token_count) >= 0.8:
            return True

    return SequenceMatcher(None, first_key, second_key).ratio() >= 0.72


def _choose_representative_sentence(sentences: List[str]) -> str:
    return max(
        sentences,
        key=lambda sentence: (
            len(_tokenize_sentence(sentence)),
            len(sentence),
        ),
    )


def _collapse_similar_sentences(sentences: List[str]) -> List[str]:
    collapsed_clusters: List[List[str]] = []

    for sentence in sentences:
        for cluster in collapsed_clusters:
            if any(_sentences_are_similar(sentence, existing) for existing in cluster):
                cluster.append(sentence)
                break
        else:
            collapsed_clusters.append([sentence])

    return [_choose_representative_sentence(cluster) for cluster in collapsed_clusters]


def _merge_texts(texts: Iterable[str]) -> str:
    unique_sentences = _deduplicate_sentences(texts)
    merged_sentences = _collapse_similar_sentences(unique_sentences)
    return " ".join(merged_sentences)


def _confidence_from_score(score: float) -> str:
    if score >= 2:
        return "high"
    if score >= 1:
        return "medium"
    return "low"


def score_predictions(predictions: list) -> dict:
    """
    Groups predictions by category, sums weights, merges text, and assigns confidence.

    Expected prediction shape:
    {
        "text": "Career growth will be slow but stable",
        "category": "career",
        "weight": 0.8
    }

    The function is also backward compatible with plain string predictions.
    """
    grouped: Dict[str, Dict[str, Any]] = {}

    for raw_prediction in predictions:
        normalized = _normalize_prediction(raw_prediction)
        if not normalized["text"]:
            continue

        category = normalized["category"]
        bucket = grouped.setdefault(
            category,
            {
                "score": 0.0,
                "texts": [],
            },
        )

        bucket["score"] += normalized["weight"]
        bucket["texts"].append(normalized["text"])

    scored_output: Dict[str, Dict[str, Any]] = {}
    for category, bucket in grouped.items():
        score = round(bucket["score"], 2)
        scored_output[category] = {
            "score": score,
            "confidence": _confidence_from_score(score),
            "summary": _merge_texts(bucket["texts"]),
        }

    return scored_output
