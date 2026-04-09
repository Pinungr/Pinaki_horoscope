from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List

from core.predictions.rule_service import compose_parashari_narrative, resolve_conflicts

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

_PLANET_STRENGTH_TARGETS = {
    "sun": 390.0,
    "moon": 360.0,
    "mars": 300.0,
    "mercury": 420.0,
    "jupiter": 390.0,
    "venus": 330.0,
    "saturn": 300.0,
    "rahu": 300.0,
    "ketu": 300.0,
}

_STRONG_OUTCOME_MIN_STRENGTH = 68.0
_MEDIUM_OUTCOME_MIN_STRENGTH = 52.0

_REINFORCING_COMBO_MIN_RULES = 2
_REINFORCING_COMBO_MIN_SCORE = 2.0

_RARE_YOGA_MARKERS = {
    "pancha_mahapurusha",
    "hamsa",
    "bhadra",
    "ruchaka",
    "malavya",
    "sasa",
    "neechabhanga",
    "dharma_karmadhipati",
    "vipareeta_raja",
    "mahabhagya",
}

_CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}

_FUNCTIONAL_ROLE_IMPACT_WEIGHTS = {
    "benefic": 0.2,
    "malefic": -0.45,
    "yogakaraka": 0.65,
    "neutral": 0.0,
}
_MAX_FUNCTIONAL_ROLE_DELTA = 0.8
_MIN_FUNCTIONAL_ROLE_MULTIPLIER = 0.2
_MAX_FUNCTIONAL_ROLE_MULTIPLIER = 2.4
_FUNCTIONAL_ROLE_POSITIVE_INVERSION_THRESHOLD = -0.4
_FUNCTIONAL_ROLE_NEGATIVE_INVERSION_THRESHOLD = 0.6

_FINAL_LAYER_DEFAULT_WEIGHTS = {
    "strength": 0.35,
    "functional_nature": 0.15,
    "lordship": 0.2,
    "yoga": 0.3,
}
_FINAL_LAYER_ORDER = ("strength", "functional_nature", "lordship", "yoga")
_SIGNAL_LAYER_ORDER = (
    "strength",
    "functional_nature",
    "lordship",
    "yoga",
    "dasha",
    "transit",
    "varga",
    "karaka",
)
_SCORE_SIGNAL_LAYERS = {"strength", "functional_nature", "lordship", "yoga"}
_MULTIPLIER_SIGNAL_LAYERS = {"dasha", "transit", "varga", "karaka"}
_KARAKA_MODIFIER_MIN = 0.5
_KARAKA_MODIFIER_MAX = 1.2
_KARAKA_BASE_MODIFIER = {
    "supportive": 1.12,
    "neutral": 1.0,
    "adverse": 0.72,
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

        effect = str(prediction.get("effect") or "positive").strip().lower()
        if effect not in {"positive", "negative"}:
            effect = "positive"

        try:
            weight = abs(float(prediction.get("weight", 1.0) or 1.0))
        except (TypeError, ValueError):
            weight = 1.0
        result_key = str(prediction.get("result_key") or prediction.get("text_key") or "").strip() or None
        raw_trace = prediction.get("trace")
        if isinstance(raw_trace, (list, tuple, set)):
            trace = [str(item).strip() for item in raw_trace if str(item).strip()]
        elif isinstance(raw_trace, str):
            trace = [raw_trace.strip()] if raw_trace.strip() else []
        else:
            trace = []

        rule_confidence = _normalize_confidence_label(prediction.get("rule_confidence", "medium"))
        allow_strength_override = bool(prediction.get("allow_strength_override", False))
        functional_lagna = str(prediction.get("functional_lagna", "")).strip().lower() or None
        functional_roles = _normalize_functional_roles(prediction.get("functional_roles"))
        karaka_payload = _derive_karaka_modifier(
            karaka_status=prediction.get("karaka_status"),
            explicit_modifier=prediction.get("karaka_modifier"),
            explicit_impact=prediction.get("karaka_impact"),
        )
    else:
        text = str(prediction).strip()
        category = "general"
        effect = "positive"
        weight = 1.0
        result_key = None
        trace = []
        rule_confidence = "medium"
        allow_strength_override = False
        functional_lagna = None
        functional_roles = []
        karaka_payload = _derive_karaka_modifier(karaka_status=None)

    return {
        "text": text,
        "category": category or "general",
        "effect": effect,
        "weight": weight,
        "result_key": result_key,
        "trace": trace,
        "rule_confidence": rule_confidence,
        "allow_strength_override": allow_strength_override,
        "functional_lagna": functional_lagna,
        "functional_roles": functional_roles,
        "karaka_modifier": karaka_payload.get("modifier", 1.0),
        "karaka_raw_modifier": karaka_payload.get("raw_modifier", 1.0),
        "karaka_impact": list(karaka_payload.get("impact", []) or []),
        "karaka_details": list(karaka_payload.get("details", []) or []),
        "karaka_source": str(karaka_payload.get("source", "neutral")),
    }


def _deduplicate_values(values: Iterable[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


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


def _extract_sentence_identifiers(sentence: str) -> set[str]:
    normalized = sentence.lower()
    identifiers: set[str] = set()

    # Handles explicit rule identifiers like "gajakesari_yoga".
    for match in re.finditer(r"\b([a-z0-9]+_yoga)\b", normalized):
        identifiers.add(match.group(1))

    # Handles natural language forms like "Gajakesari Yoga".
    for match in re.finditer(r"\b([a-z0-9]+)\s+yoga\b", normalized):
        identifiers.add(f"{match.group(1)}_yoga")

    return identifiers


def _sentences_are_similar(first: str, second: str) -> bool:
    first_key = _normalize_sentence_key(first)
    second_key = _normalize_sentence_key(second)

    if not first_key or not second_key:
        return False
    if first_key == second_key:
        return True

    identifiers_in_first = _extract_sentence_identifiers(first)
    identifiers_in_second = _extract_sentence_identifiers(second)

    # Keep identifier-bearing summaries distinct so names like "gajakesari" stay visible.
    if identifiers_in_first != identifiers_in_second:
        return False

    similarity_threshold = 0.82
    token_overlap_threshold = 0.9
    if identifiers_in_first:
        # Same identifier, slightly more permissive collapse for paraphrased duplicates.
        similarity_threshold = 0.6
        token_overlap_threshold = 0.6

    first_tokens = _tokenize_sentence(first)
    second_tokens = _tokenize_sentence(second)
    if first_tokens and second_tokens:
        shared_tokens = len(first_tokens & second_tokens)
        min_token_count = min(len(first_tokens), len(second_tokens))
        if min_token_count and (shared_tokens / min_token_count) >= token_overlap_threshold:
            return True

    return SequenceMatcher(None, first_key, second_key).ratio() >= similarity_threshold


def _choose_representative_sentence(sentences: List[str]) -> str:
    return max(
        sentences,
        key=lambda sentence: (
            len(_extract_sentence_identifiers(sentence)),
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


def _merge_conflicting_texts(positive_texts: Iterable[str], negative_texts: Iterable[str], net_score: float) -> str:
    """Builds a readable summary when both positive and negative rules match."""
    positive_summary = _merge_texts(positive_texts)
    negative_summary = _merge_texts(negative_texts)

    if positive_summary and negative_summary:
        if net_score > 0:
            return f"{positive_summary} However, {negative_summary}"
        if net_score < 0:
            return f"{negative_summary} Still, {positive_summary}"
        return f"{positive_summary} At the same time, {negative_summary}"
    return positive_summary or negative_summary


def _confidence_from_score(score: float) -> str:
    magnitude = abs(score)
    if magnitude >= 2:
        return "high"
    if magnitude >= 1:
        return "medium"
    return "low"


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def compose_temporal_score(
    base_score: Any,
    dasha_activation: Any,
    transit_modifier: Any,
    varga_concordance: Any = 1.0,
    karaka_modifier: Any = 1.0,
    *,
    max_uplift_ratio: float = 1.5,
) -> Dict[str, Any]:
    """
    Composes temporal scoring with deterministic bounds.

    Formula:
    final_score = base_score * dasha_activation * transit_modifier * varga_concordance * karaka_modifier

    Guardrails:
    - clamps activation multipliers to avoid runaway amplification/suppression
    - caps maximum uplift relative to natal promise strength
    - never allows negative final score
    """
    base = max(0.0, _safe_float(base_score))
    dasha = _clamp(_safe_float(dasha_activation) or 1.0, 0.6, 1.4)
    transit = _clamp(_safe_float(transit_modifier) or 1.0, 0.7, 1.35)
    concordance = _clamp(_safe_float(varga_concordance) or 1.0, 0.75, 1.25)
    karaka = _clamp(_safe_float(karaka_modifier) or 1.0, _KARAKA_MODIFIER_MIN, _KARAKA_MODIFIER_MAX)
    raw_score = base * dasha * transit * concordance * karaka

    if base <= 0.0:
        final_score = 0.0
        cap_applied = False
    else:
        uplift_cap = base * max(1.0, _safe_float(max_uplift_ratio) or 1.5)
        bounded = min(raw_score, uplift_cap, 100.0)
        final_score = max(0.0, bounded)
        cap_applied = bounded < raw_score

    return {
        "base_score": round(base, 2),
        "dasha_activation": round(dasha, 3),
        "transit_modifier": round(transit, 3),
        "varga_concordance": round(concordance, 3),
        "karaka_modifier": round(karaka, 3),
        "raw_score": round(raw_score, 2),
        "final_score": int(round(final_score)),
        "cap_applied": cap_applied,
        "max_uplift_ratio": round(max(1.0, _safe_float(max_uplift_ratio) or 1.5), 2),
    }


def compute_final_prediction(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes one final prediction score from M1-M7 layer outputs.

    Expected context payload:
    {
        "prediction": str,
        "base_strength": float,       # M1
        "functional_weight": float,   # M2 multiplier-like value
        "lordship_score": float,      # M3
        "yoga_score": float,          # M4
        "dasha_activation": float,    # M5
        "transit_modifier": float,    # M6
        "varga_concordance": float,   # M7
        "karaka_status": list,        # M10 diagnostics (optional)
        "karaka_modifier": float,     # M10 override/input (optional)
        "karaka_impact": list,        # M10 reasoning lines (optional)
        "scoring_weights": { ... }    # Optional deterministic override
    }
    """
    payload = dict(context or {})

    weights = _normalize_final_layer_weights(payload.get("scoring_weights"))
    raw_base_strength = _normalize_layer_score(payload.get("base_strength"), fallback=0.0)
    raw_functional_weight = _clamp(_safe_float(payload.get("functional_weight") or 1.0), 0.6, 1.4)
    raw_functional_score = _functional_weight_to_score(raw_functional_weight)
    raw_lordship_score = _normalize_layer_score(payload.get("lordship_score"), fallback=50.0)
    raw_yoga_score = _normalize_layer_score(payload.get("yoga_score"), fallback=raw_base_strength)
    raw_dasha_activation = _safe_float(payload.get("dasha_activation", 1.0)) or 1.0
    raw_transit_modifier = _safe_float(payload.get("transit_modifier", 1.0)) or 1.0
    raw_varga_concordance = _safe_float(payload.get("varga_concordance", 1.0)) or 1.0
    karaka_payload = _derive_karaka_modifier(
        karaka_status=payload.get("karaka_status"),
        explicit_modifier=payload.get("karaka_modifier"),
        explicit_impact=payload.get("karaka_impact"),
    )
    raw_karaka_modifier = _clamp_karaka_modifier(karaka_payload.get("modifier", 1.0))

    signal_normalization = _apply_signal_normalization(
        {
            "strength": raw_base_strength,
            "functional_nature": raw_functional_score,
            "lordship": raw_lordship_score,
            "yoga": raw_yoga_score,
            "dasha": raw_dasha_activation,
            "transit": raw_transit_modifier,
            "varga": raw_varga_concordance,
            "karaka": raw_karaka_modifier,
        },
        payload.get("signal_layers"),
    )
    adjusted_layers = signal_normalization.get("adjusted_values", {})
    if not isinstance(adjusted_layers, dict):
        adjusted_layers = {}

    base_strength = _normalize_layer_score(adjusted_layers.get("strength"), fallback=raw_base_strength)
    functional_score = _normalize_layer_score(
        adjusted_layers.get("functional_nature"),
        fallback=raw_functional_score,
    )
    functional_weight = _score_to_functional_weight(functional_score)
    lordship_score = _normalize_layer_score(adjusted_layers.get("lordship"), fallback=raw_lordship_score)
    yoga_score = _normalize_layer_score(adjusted_layers.get("yoga"), fallback=raw_yoga_score)
    dasha_activation = _safe_float(adjusted_layers.get("dasha", raw_dasha_activation)) or 1.0
    transit_modifier = _safe_float(adjusted_layers.get("transit", raw_transit_modifier)) or 1.0
    varga_concordance = _safe_float(adjusted_layers.get("varga", raw_varga_concordance)) or 1.0
    karaka_modifier = _clamp_karaka_modifier(adjusted_layers.get("karaka", raw_karaka_modifier))

    strength_component = round(base_strength * weights["strength"], 3)
    functional_component = round(functional_score * weights["functional_nature"], 3)
    lordship_component = round(lordship_score * weights["lordship"], 3)
    yoga_component = round(yoga_score * weights["yoga"], 3)
    weighted_base = round(
        strength_component + functional_component + lordship_component + yoga_component,
        3,
    )

    temporal_score = compose_temporal_score(
        weighted_base,
        dasha_activation,
        transit_modifier,
        varga_concordance,
        karaka_modifier,
    )

    final_score = int(temporal_score.get("final_score", 0))
    prediction_text = str(payload.get("prediction", "")).strip()

    trace = {
        "strength": {
            "raw_input_score": round(raw_base_strength, 2),
            "input_score": round(base_strength, 2),
            "weight": round(weights["strength"], 3),
            "weighted_contribution": round(strength_component, 3),
            "reasoning": "Planetary strength (Shadbala) provides the foundational capacity of the indicator.",
        },
        "functional_nature": {
            "raw_input_multiplier": round(raw_functional_weight, 3),
            "raw_normalized_score": round(raw_functional_score, 2),
            "input_multiplier": round(functional_weight, 3),
            "normalized_score": round(functional_score, 2),
            "weight": round(weights["functional_nature"], 3),
            "weighted_contribution": round(functional_component, 3),
            "reasoning": "Functional nature (Benefic/Malefic role for Lagna) modifies how the planet expresses its energy.",
        },
        "lordship": {
            "raw_input_score": round(raw_lordship_score, 2),
            "input_score": round(lordship_score, 2),
            "weight": round(weights["lordship"], 3),
            "weighted_contribution": round(lordship_component, 3),
            "reasoning": "House lordship and placement determine the specific lifecycle areas affected.",
        },
        "yoga": {
            "raw_input_score": round(raw_yoga_score, 2),
            "input_score": round(yoga_score, 2),
            "weight": round(weights["yoga"], 3),
            "weighted_contribution": round(yoga_component, 3),
            "reasoning": "Astrological combinations (Yogas) provide specific pattern-based directional strength.",
        },
        "dasha": {
            "raw_multiplier": round(raw_dasha_activation, 3),
            "multiplier": temporal_score.get("dasha_activation", 1.0),
            "reasoning": "Vimshottari Dasha timing determines if the natal promise is currently active.",
        },
        "transit": {
            "raw_multiplier": round(raw_transit_modifier, 3),
            "multiplier": temporal_score.get("transit_modifier", 1.0),
            "reasoning": "Transits (Gochar) act as triggers for immediate activation of the dasha promise.",
        },
        "varga": {
            "raw_multiplier": round(raw_varga_concordance, 3),
            "multiplier": temporal_score.get("varga_concordance", 1.0),
            "reasoning": "Divisional chart agreement (Navamsha/Dashamsha) confirms if the internal core supports the outcome.",
        },
        "karaka": {
            "raw_multiplier": round(raw_karaka_modifier, 3),
            "multiplier": temporal_score.get("karaka_modifier", 1.0),
            "source": str(karaka_payload.get("source", "neutral")),
            "impact": [str(line).strip() for line in karaka_payload.get("impact", []) if str(line).strip()],
            "details": list(karaka_payload.get("details", [])),
            "reasoning": "Natural significators (Karakas) provide the universal support for the specific matter.",
        },
        "deduplication": signal_normalization.get("trace", {}),
        "weighted_base_score": round(weighted_base, 2),
        "formula": (
            "weighted_base = "
            "(strength*w_strength) + "
            "(functional_score*w_functional) + "
            "(lordship*w_lordship) + "
            "(yoga*w_yoga); "
            "final = weighted_base * dasha * transit * varga * karaka"
        ),
    }

    return {
        "prediction": prediction_text,
        "final_score": final_score,
        "rank": None,
        "trace": trace,
        "score_components": {
            "weighted_base_score": round(weighted_base, 2),
            "temporal": temporal_score,
            "deduplication": signal_normalization,
        },
    }


def rank_predictions_deterministically(predictions: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deterministically ranks rows by final score (desc) with stable tie-breaks.
    Applies M9 conflict resolution on each row before ranking.
    """
    indexed_rows: List[tuple[int, Dict[str, Any], float, str, str, str]] = []
    for index, raw in enumerate(predictions or []):
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
        score = _safe_float(row.get("final_score", row.get("score", 0.0)))
        conflict_signals = _extract_conflict_signals(row)
        resolution = resolve_conflicts(conflict_signals)

        score_multiplier = _safe_float(resolution.get("score_multiplier")) or 1.0
        confidence_multiplier = _safe_float(resolution.get("confidence_multiplier")) or 1.0
        resolved_score = max(0.0, score * score_multiplier)
        if str(resolution.get("dominant_outcome", "")).strip().lower() == "suppressed":
            resolved_score = 0.0

        confidence_score = max(0.0, min(100.0, resolved_score * max(0.0, confidence_multiplier)))
        resolution_confidence = _confidence_from_prediction_score(confidence_score)

        final_prediction = str(
            row.get("prediction", row.get("text", ""))
        ).strip()
        if str(resolution.get("dominant_outcome", "")).strip().lower() == "suppressed":
            final_prediction = ""

        row["resolution"] = resolution
        row["dominant_outcome"] = resolution.get("dominant_outcome", "valid")
        row["dominant_reasoning"] = str(resolution.get("dominant_reasoning", "")).strip()
        row["suppressed_signals"] = list(resolution.get("suppressed_factors", []) or [])
        row["suppressed_factors"] = list(resolution.get("suppressed_factors", []) or [])
        row["resolution_explanation"] = str(resolution.get("resolution_explanation", "")).strip()
        row["final_prediction"] = final_prediction
        row["resolution_confidence_score"] = round(confidence_score, 2)
        row["resolution_confidence"] = resolution_confidence
        row["resolved_score_multiplier"] = round(score_multiplier, 6)
        row["resolved_confidence_multiplier"] = round(confidence_multiplier, 6)
        row["is_suppressed"] = bool(
            str(resolution.get("dominant_outcome", "")).strip().lower() == "suppressed"
        )
        row["final_score"] = int(round(resolved_score))
        row["score"] = int(round(resolved_score))
        row.update(compose_parashari_narrative(row))

        score = resolved_score
        yoga_key = _normalize_identifier(row.get("yoga", ""))
        area_key = _normalize_identifier(row.get("area", ""))
        text_key = _normalize_identifier(row.get("final_prediction", row.get("prediction", row.get("text", ""))))
        indexed_rows.append((index, row, score, yoga_key, area_key, text_key))

    ranked = sorted(
        indexed_rows,
        key=lambda item: (-item[2], item[3], item[4], item[5], item[0]),
    )

    output: List[Dict[str, Any]] = []
    for rank, (_, row, score, _, _, _) in enumerate(ranked, start=1):
        normalized_row = dict(row)
        normalized_row["final_score"] = int(round(score))
        normalized_row["score"] = int(round(score))
        normalized_row["rank"] = rank
        output.append(normalized_row)
    return output


def get_varga_concordance(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes agreement across D1, D9, and D10 in an interpretable way.
    """
    payload = dict(context or {})

    d1_signal = _coerce_direction(payload.get("d1_signal"), score=payload.get("d1_score"))
    d9_signal = _coerce_direction(payload.get("d9_signal"), score=payload.get("d9_score"))
    d10_signal = _coerce_direction(payload.get("d10_signal"), score=payload.get("d10_score"))

    score = 0.5
    factors: List[str] = []
    area = str(payload.get("area", "general") or "general").strip().lower() or "general"

    if d10_signal == 1 and d1_signal == 1:
        score += 0.10
        factors.append(f"Societal execution (D10) confirms the directional promise of the natal chart (D1) for {area}.")
    elif d10_signal == -1 and d1_signal == 1:
        score -= 0.10
        factors.append(f"Execution potential (D10) conflicts with the primary natal promise in {area}.")
    elif d10_signal == 0:
        factors.append("External execution factors (D10) remain neutral.")

    if d9_signal == 1 and d1_signal == 1:
        score += 0.30
        factors.append("Internal core strength (D9) provides a strong foundation for the natal promise.")
    elif d9_signal == -1 and d1_signal == 1:
        score -= 0.30
        factors.append("Weakness in the internal core (D9) suggests friction in realizing the natal promise.")
    elif d9_signal == 0:
        factors.append("Internal foundational support (D9) is neutral.")

    active_signals = [s for s in [d1_signal, d9_signal, d10_signal] if s != 0]
    if len(active_signals) >= 2 and all(s == active_signals[0] for s in active_signals):
        score += 0.1
        factors.append("The natal, foundational, and execution layers show coherent directional agreement.")
    elif len(active_signals) >= 2 and len(set(active_signals)) > 1:
        score -= 0.1
        factors.append("Divergence between internal and external layers suggests a need for balanced interpretation.")

    score = _clamp(score, 0.0, 1.0)
    if score >= 0.75:
        level = "high"
        modifier = 1.12 + min(0.08, (score - 0.75) * 0.32)
    elif score >= 0.4:
        level = "medium"
        modifier = 0.96 + ((score - 0.4) / 0.35) * 0.12
    else:
        level = "low"
        modifier = 0.8 + (score / 0.4) * 0.16

    return {
        "concordance_score": round(score, 3),
        "agreement_level": level,
        "contributing_factors": _deduplicate_values(factors)[:8],
        "concordance_modifier": round(_clamp(modifier, 0.8, 1.2), 3),
    }


def _coerce_direction(raw_signal: Any, *, score: Any = None) -> int:
    signal = str(raw_signal or "").strip().lower()
    if signal in {"support", "supportive", "confirm", "aligned", "high", "positive", "strong"}:
        return 1
    if signal in {"conflict", "low", "negative", "weak", "suppressed", "suppressing"}:
        return -1
    if signal in {"neutral", "medium", ""}:
        # Keep reading numeric score before returning neutral.
        pass

    numeric = _safe_float(score)
    if numeric >= 0.2:
        return 1
    if numeric <= -0.2:
        return -1
    return 0


def _normalize_confidence_label(value: Any) -> str:
    normalized = str(value or "medium").strip().lower() or "medium"
    return normalized if normalized in _CONFIDENCE_ORDER else "medium"


def _extract_conflict_signals(row: Dict[str, Any]) -> Dict[str, Any]:
    strength_score = _safe_float(
        row.get("strength_score", _safe_float(_read_nested(row, ["trace", "strength", "input_score"], 0.0)))
    )
    if strength_score >= 68.0:
        strength_level = "strong"
    elif strength_score >= 52.0:
        strength_level = "medium"
    else:
        strength_level = "weak"

    timing = row.get("timing", {}) if isinstance(row.get("timing"), dict) else {}
    dasha_level = str(
        timing.get("activation_level", timing.get("relevance", "low"))
    ).strip().lower() or "low"

    lordship_score = _safe_float(row.get("lordship_score", 50.0))
    if lordship_score >= 65.0:
        house_state = "strong"
    elif lordship_score <= 40.0:
        house_state = "weak"
    else:
        house_state = "neutral"

    yoga_state = str(row.get("state", "neutral")).strip().lower() or "neutral"
    yoga_id = str(row.get("yoga", "")).strip().lower()
    yoga_cancelled = yoga_state in {"cancelled", "bhanga"} or "bhanga" in yoga_id

    varga_agreement = str(row.get("agreement_level", "medium")).strip().lower() or "medium"
    varga_score = _safe_float(row.get("concordance_score", 0.5))

    transit = row.get("transit", {}) if isinstance(row.get("transit"), dict) else {}
    transit_state = str(transit.get("support_state", "neutral")).strip().lower() or "neutral"
    transit_level = str(transit.get("trigger_level", "low")).strip().lower() or "low"

    return {
        "strength_gate": {
            "score": strength_score,
            "level": strength_level,
        },
        "dasha_activation": {
            "level": dasha_level,
            "multiplier": _safe_float(row.get("dasha_activation", 1.0)),
        },
        "house_lord_condition": {
            "score": lordship_score,
            "state": house_state,
        },
        "yoga_status": {
            "state": yoga_state,
            "score": _safe_float(row.get("yoga_score", 0.0)),
            "is_cancelled": yoga_cancelled,
        },
        "varga_concordance": {
            "agreement_level": varga_agreement,
            "score": varga_score,
        },
        "transit_trigger": {
            "support_state": transit_state,
            "trigger_level": transit_level,
        },
    }


def _read_nested(payload: Any, path: List[str], default: Any = None) -> Any:
    current = payload
    for key in path:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return current if current is not None else default


def _confidence_from_prediction_score(score: float) -> str:
    bounded = max(0.0, min(100.0, _safe_float(score)))
    if bounded >= 75.0:
        return "high"
    if bounded >= 45.0:
        return "medium"
    return "low"


def _normalize_final_layer_weights(raw_weights: Any) -> Dict[str, float]:
    if isinstance(raw_weights, dict):
        source = {
            key: _safe_float(raw_weights.get(key, _FINAL_LAYER_DEFAULT_WEIGHTS[key]))
            for key in _FINAL_LAYER_ORDER
        }
    else:
        source = dict(_FINAL_LAYER_DEFAULT_WEIGHTS)

    bounded = {
        key: max(0.0, source.get(key, 0.0))
        for key in _FINAL_LAYER_ORDER
    }
    total = sum(bounded.values())
    if total <= 0:
        return dict(_FINAL_LAYER_DEFAULT_WEIGHTS)

    return {
        key: round(bounded[key] / total, 6)
        for key in _FINAL_LAYER_ORDER
    }


def _normalize_layer_score(value: Any, *, fallback: float = 0.0) -> float:
    normalized = _safe_float(value if value is not None else fallback)
    return round(_clamp(normalized, 0.0, 100.0), 3)


def _functional_weight_to_score(functional_weight: float) -> float:
    # 0.6 -> 0, 1.0 -> 50, 1.4 -> 100
    normalized = (float(functional_weight) - 0.6) / 0.8
    return round(_clamp(normalized * 100.0, 0.0, 100.0), 3)


def _score_to_functional_weight(functional_score: float) -> float:
    normalized_score = _clamp(_safe_float(functional_score), 0.0, 100.0)
    return round(_clamp(0.6 + ((normalized_score / 100.0) * 0.8), 0.6, 1.4), 3)


def _clamp_karaka_modifier(value: Any) -> float:
    return round(_clamp(_safe_float(value) or 1.0, _KARAKA_MODIFIER_MIN, _KARAKA_MODIFIER_MAX), 6)


def _normalize_karaka_status(raw_karaka_status: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_karaka_status, (list, tuple)):
        return []

    normalized_rows: List[Dict[str, Any]] = []
    for raw in raw_karaka_status:
        if not isinstance(raw, dict):
            continue
        planet = str(raw.get("planet") or raw.get("karaka_planet") or "").strip().lower()
        if not planet:
            continue
        contribution = str(raw.get("contribution", "neutral")).strip().lower() or "neutral"
        if contribution not in _KARAKA_BASE_MODIFIER:
            contribution = "neutral"
        strength_status = str(raw.get("strength_status", "medium")).strip().lower() or "medium"
        if strength_status not in {"strong", "medium", "weak"}:
            strength_status = "medium"
        dignity = str(raw.get("dignity", "neutral")).strip().lower() or "neutral"
        afflictions = raw.get("affliction_flags", {})
        if not isinstance(afflictions, dict):
            afflictions = {}

        normalized_rows.append(
            {
                "planet": planet,
                "contribution": contribution,
                "strength_status": strength_status,
                "dignity": dignity,
                "affliction_flags": {
                    "is_afflicted": bool(afflictions.get("is_afflicted", False)),
                    "conjunct_malefic": bool(afflictions.get("conjunct_malefic", False)),
                    "malefic_aspect": bool(afflictions.get("malefic_aspect", False)),
                    "combust": bool(afflictions.get("combust", False)),
                },
            }
        )
    return normalized_rows


def _karaka_row_modifier(row: Dict[str, Any]) -> float:
    contribution = str(row.get("contribution", "neutral"))
    strength_status = str(row.get("strength_status", "medium"))
    dignity = str(row.get("dignity", "neutral"))
    afflictions = row.get("affliction_flags", {}) if isinstance(row.get("affliction_flags"), dict) else {}

    modifier = _KARAKA_BASE_MODIFIER.get(contribution, 1.0)
    if strength_status == "strong":
        modifier += 0.04
    elif strength_status == "weak":
        modifier -= 0.08

    dignity_delta = {
        "exalted": 0.05,
        "own": 0.03,
        "friendly": 0.01,
        "neutral": 0.0,
        "enemy": -0.04,
        "debilitated": -0.08,
    }.get(dignity, 0.0)
    modifier += dignity_delta

    affliction_penalty = 0.0
    if bool(afflictions.get("is_afflicted")):
        affliction_penalty += 0.08
    if bool(afflictions.get("conjunct_malefic")):
        affliction_penalty += 0.02
    if bool(afflictions.get("malefic_aspect")):
        affliction_penalty += 0.02
    if bool(afflictions.get("combust")):
        affliction_penalty += 0.03
    modifier -= min(0.15, affliction_penalty)
    return _clamp_karaka_modifier(modifier)


def _derive_karaka_modifier(
    *,
    karaka_status: Any,
    explicit_modifier: Any = None,
    explicit_impact: Any = None,
) -> Dict[str, Any]:
    normalized_rows = _normalize_karaka_status(karaka_status)
    if not normalized_rows:
        explicit = _safe_float(explicit_modifier)
        has_explicit = explicit_modifier is not None and explicit > 0.0
        resolved = _clamp_karaka_modifier(explicit if has_explicit else 1.0)
        impact_lines = []
        if isinstance(explicit_impact, (list, tuple)):
            impact_lines = [str(line).strip() for line in explicit_impact if str(line).strip()]
        return {
            "modifier": resolved,
            "raw_modifier": resolved,
            "impact": impact_lines,
            "details": [],
            "source": "explicit" if has_explicit else "neutral",
        }

    seen_counts: Dict[str, int] = {}
    weighted_total = 0.0
    weight_sum = 0.0
    min_modifier = _KARAKA_MODIFIER_MAX
    details: List[Dict[str, Any]] = []
    impact: List[str] = []

    for row in normalized_rows:
        planet = str(row.get("planet", "unknown"))
        occurrence = seen_counts.get(planet, 0)
        seen_counts[planet] = occurrence + 1
        dedupe_factor = round(1.0 / float(2 ** occurrence), 6)

        row_modifier = _karaka_row_modifier(row)
        weighted_total += row_modifier * dedupe_factor
        weight_sum += dedupe_factor
        min_modifier = min(min_modifier, row_modifier)

        trend = "supporting" if row_modifier > 1.03 else "reducing" if row_modifier < 0.97 else "balancing"
        reason = (
            f"{planet.capitalize()} {row.get('contribution', 'neutral')} -> {trend} "
            f"({row.get('strength_status', 'medium')} strength, {row.get('dignity', 'neutral')} dignity)."
        )
        if dedupe_factor < 1.0:
            reason = f"{reason[:-1]} overlap weight {dedupe_factor:.2f}."
        impact.append(reason)
        details.append(
            {
                "planet": planet,
                "modifier": round(row_modifier, 3),
                "dedupe_factor": dedupe_factor,
                "contribution": row.get("contribution"),
                "strength_status": row.get("strength_status"),
                "dignity": row.get("dignity"),
                "is_afflicted": bool((row.get("affliction_flags") or {}).get("is_afflicted", False)),
            }
        )

    if weight_sum <= 0.0:
        return {
            "modifier": 1.0,
            "raw_modifier": 1.0,
            "impact": [],
            "details": [],
            "source": "neutral",
        }

    weighted_average = weighted_total / weight_sum
    raw_modifier = _clamp_karaka_modifier((0.7 * weighted_average) + (0.3 * min_modifier))
    explicit = _safe_float(explicit_modifier)
    if explicit_modifier is not None and explicit > 0.0:
        explicit_clamped = _clamp_karaka_modifier(explicit)
        # Deterministic blend keeps explicit override bounded by diagnostics.
        resolved = _clamp_karaka_modifier((0.75 * raw_modifier) + (0.25 * explicit_clamped))
        source = "status+explicit"
    else:
        resolved = raw_modifier
        source = "status"

    impact.append(
        f"Karaka moderation blended with min-dominance; final modifier {resolved:.3f}."
    )
    return {
        "modifier": resolved,
        "raw_modifier": raw_modifier,
        "impact": impact[:10],
        "details": details,
        "source": source,
    }


def _normalize_signal_layers(raw_signal_layers: Any) -> Dict[str, List[Dict[str, Any]]]:
    if not isinstance(raw_signal_layers, dict):
        return {layer: [] for layer in _SIGNAL_LAYER_ORDER}

    normalized_layers: Dict[str, List[Dict[str, Any]]] = {layer: [] for layer in _SIGNAL_LAYER_ORDER}
    for layer in _SIGNAL_LAYER_ORDER:
        rows = raw_signal_layers.get(layer, [])
        if not isinstance(rows, (list, tuple)):
            continue
        for raw in rows:
            normalized = _normalize_signal_identity(raw, default_concept_type=layer)
            if normalized is None:
                continue
            normalized_layers[layer].append(normalized)
    return normalized_layers


def _normalize_signal_identity(raw_signal: Any, *, default_concept_type: str) -> Dict[str, Any] | None:
    if not isinstance(raw_signal, dict):
        return None

    planet = str(raw_signal.get("planet", "") or "").strip().lower() or "*"
    house = _normalize_signal_house(raw_signal.get("house"))
    concept_type = str(raw_signal.get("concept_type", default_concept_type) or default_concept_type).strip().lower()
    if not concept_type:
        concept_type = default_concept_type

    return {
        "planet": planet,
        "house": house,
        "concept_type": concept_type,
        "signal_id": {
            "planet": planet,
            "house": house,
            "concept_type": concept_type,
        },
    }


def _normalize_signal_house(value: Any) -> int | None:
    try:
        house = int(value)
    except (TypeError, ValueError):
        return None
    if 1 <= house <= 12:
        return house
    return None


def _apply_signal_normalization(
    layer_values: Dict[str, float],
    raw_signal_layers: Any,
) -> Dict[str, Any]:
    signal_layers = _normalize_signal_layers(raw_signal_layers)
    seen_full_ids: set[tuple[str, int | None, str]] = set()
    overlap_counts: Dict[tuple[str, int | None], int] = {}

    layer_details: Dict[str, Dict[str, Any]] = {}
    adjusted_values: Dict[str, float] = {}
    summary_lines: List[str] = []

    for layer in _SIGNAL_LAYER_ORDER:
        signals = signal_layers.get(layer, [])
        signal_rows: List[Dict[str, Any]] = []
        signal_factors: List[float] = []
        full_duplicates = 0
        partial_overlaps = 0

        for signal in signals:
            planet = str(signal.get("planet", "*"))
            house = signal.get("house")
            concept_type = str(signal.get("concept_type", layer))
            full_key = (planet, house, concept_type)
            overlap_key = (planet, house)

            if full_key in seen_full_ids:
                factor = 0.0
                reason = "full_duplicate"
                full_duplicates += 1
            else:
                overlap_index = overlap_counts.get(overlap_key, 0)
                factor = round(1.0 / float(2 ** overlap_index), 6)
                overlap_counts[overlap_key] = overlap_index + 1
                seen_full_ids.add(full_key)
                if overlap_index == 0:
                    reason = "primary"
                else:
                    reason = f"partial_overlap_{overlap_index + 1}"
                    partial_overlaps += 1

            signal_factors.append(factor)
            signal_rows.append(
                {
                    "planet": planet,
                    "house": house,
                    "concept_type": concept_type,
                    "dedupe_factor": factor,
                    "reason": reason,
                    "signal_id": {
                        "planet": planet,
                        "house": house,
                        "concept_type": concept_type,
                    },
                }
            )

        if signal_factors:
            layer_factor = round(sum(signal_factors) / len(signal_factors), 6)
        else:
            layer_factor = 1.0

        if layer in _SCORE_SIGNAL_LAYERS:
            default_raw = 0.0
        elif layer in _MULTIPLIER_SIGNAL_LAYERS:
            default_raw = 1.0
        else:
            default_raw = 0.0
        raw_value = _safe_float(layer_values.get(layer, default_raw))
        adjusted_value = _apply_layer_factor(layer, raw_value, layer_factor)
        adjusted_values[layer] = adjusted_value

        if full_duplicates > 0:
            summary_lines.append(
                f"{layer}: {full_duplicates} full duplicate signal(s) counted once; repeated signals reduced."
            )
        elif partial_overlaps > 0:
            summary_lines.append(
                f"{layer}: {partial_overlaps} overlapping signal(s) reduced using diminishing weights (1.0, 0.5, 0.25...)."
            )

        layer_details[layer] = {
            "raw_value": round(raw_value, 6),
            "adjusted_value": round(adjusted_value, 6),
            "dedupe_factor": round(layer_factor, 6),
            "signal_count": len(signal_rows),
            "full_duplicates": full_duplicates,
            "partial_overlaps": partial_overlaps,
            "suppression_applied": bool(layer_factor < 1.0),
            "signals": signal_rows,
        }

    if not summary_lines:
        summary_lines.append("No overlapping signals detected; no deduplication suppression applied.")

    return {
        "adjusted_values": adjusted_values,
        "trace": {
            "summary": summary_lines,
            "layers": layer_details,
            "strategy": {
                "full_duplicate": "count_once",
                "partial_overlap": "diminishing_weights",
                "diminishing_sequence": [1.0, 0.5, 0.25],
            },
        },
    }


def _apply_layer_factor(layer: str, raw_value: float, dedupe_factor: float) -> float:
    if layer in _SCORE_SIGNAL_LAYERS:
        return round(raw_value * dedupe_factor, 6)
    if layer in _MULTIPLIER_SIGNAL_LAYERS:
        # Pull repeated temporal modifiers toward neutral 1.0.
        return round(1.0 + ((raw_value - 1.0) * dedupe_factor), 6)
    return round(raw_value, 6)


def _normalize_functional_roles(raw_roles: Any) -> List[Dict[str, str]]:
    normalized_roles: List[Dict[str, str]] = []
    seen: set[str] = set()

    if isinstance(raw_roles, dict):
        role_items = [
            {"planet": str(planet), "role": str(role)}
            for planet, role in raw_roles.items()
        ]
    elif isinstance(raw_roles, (list, tuple, set)):
        role_items = list(raw_roles)
    else:
        role_items = []

    for item in role_items:
        if isinstance(item, dict):
            planet = str(item.get("planet", "")).strip().lower()
            role = str(item.get("role", "neutral")).strip().lower() or "neutral"
        else:
            planet = str(item).strip().lower()
            role = "neutral"

        if not planet:
            continue
        if role not in _FUNCTIONAL_ROLE_IMPACT_WEIGHTS:
            role = "neutral"

        signature = f"{planet}:{role}"
        if signature in seen:
            continue
        seen.add(signature)
        normalized_roles.append({"planet": planet, "role": role})

    return normalized_roles


def _format_lagna_name(lagna: str | None) -> str:
    normalized = str(lagna or "").strip().lower()
    if not normalized:
        return "this"
    return normalized.capitalize()


def _build_functional_role_sentence(
    lagna: str | None,
    functional_roles: List[Dict[str, str]],
) -> str:
    if not functional_roles:
        return ""

    chunks = [
        f"{role['planet'].capitalize()} acts as functional {role['role']}"
        for role in functional_roles
    ]
    if len(chunks) == 1:
        role_text = chunks[0]
    elif len(chunks) == 2:
        role_text = f"{chunks[0]} and {chunks[1]}"
    else:
        role_text = ", ".join(chunks[:-1]) + f", and {chunks[-1]}"

    lagna_name = _format_lagna_name(lagna)
    if lagna_name == "this":
        return f"{role_text} for this Lagna."
    return f"{role_text} for {lagna_name} Lagna."


def _clamp_role_multiplier(value: float) -> float:
    return max(
        _MIN_FUNCTIONAL_ROLE_MULTIPLIER,
        min(_MAX_FUNCTIONAL_ROLE_MULTIPLIER, value),
    )


def _apply_functional_role_impact(normalized_prediction: Dict[str, Any]) -> Dict[str, Any]:
    functional_roles = [
        item
        for item in normalized_prediction.get("functional_roles", [])
        if isinstance(item, dict) and item.get("role") in _FUNCTIONAL_ROLE_IMPACT_WEIGHTS
    ]
    non_neutral_roles = [item for item in functional_roles if item.get("role") != "neutral"]
    if not non_neutral_roles:
        return {
            "effect": normalized_prediction["effect"],
            "weight": normalized_prediction["weight"],
            "trace_lines": [],
            "summary_note": "",
            "impact": None,
        }

    role_delta = sum(
        _FUNCTIONAL_ROLE_IMPACT_WEIGHTS[item["role"]]
        for item in non_neutral_roles
    ) / float(len(non_neutral_roles))
    role_delta = max(-_MAX_FUNCTIONAL_ROLE_DELTA, min(_MAX_FUNCTIONAL_ROLE_DELTA, role_delta))

    original_effect = str(normalized_prediction.get("effect", "positive"))
    adjusted_effect = original_effect

    if (
        original_effect == "positive"
        and role_delta <= _FUNCTIONAL_ROLE_POSITIVE_INVERSION_THRESHOLD
    ):
        adjusted_effect = "negative"
    elif (
        original_effect == "negative"
        and role_delta >= _FUNCTIONAL_ROLE_NEGATIVE_INVERSION_THRESHOLD
    ):
        adjusted_effect = "positive"

    if adjusted_effect == original_effect:
        if original_effect == "negative":
            role_multiplier = _clamp_role_multiplier(1.0 - role_delta)
        else:
            role_multiplier = _clamp_role_multiplier(1.0 + role_delta)
    else:
        role_multiplier = _clamp_role_multiplier(1.0 + (abs(role_delta) * 0.75))

    adjusted_weight = round(
        _safe_float(normalized_prediction.get("weight", 0.0)) * role_multiplier,
        4,
    )

    role_sentence = _build_functional_role_sentence(
        normalized_prediction.get("functional_lagna"),
        non_neutral_roles,
    )
    if adjusted_effect != original_effect:
        action_note = f"Effect flipped {original_effect} -> {adjusted_effect}"
    else:
        action_note = f"Effect remained {adjusted_effect}"

    trace_line = (
        f"Functional role impact: {role_sentence} "
        f"{action_note}; role multiplier x{role_multiplier:.2f}."
    ).strip()

    summary_note = (
        f"{role_sentence} This adjusted the outcome weighting by x{role_multiplier:.2f}."
    ).strip()
    if adjusted_effect != original_effect:
        summary_note = f"{summary_note} The interpreted effect shifted to {adjusted_effect}."

    dominant_role = max(
        non_neutral_roles,
        key=lambda item: abs(_FUNCTIONAL_ROLE_IMPACT_WEIGHTS[item["role"]]),
    )["role"]

    return {
        "effect": adjusted_effect,
        "weight": adjusted_weight,
        "trace_lines": [trace_line],
        "summary_note": summary_note,
        "impact": {
            "lagna": normalized_prediction.get("functional_lagna"),
            "roles": non_neutral_roles,
            "dominant_role": dominant_role,
            "role_delta": round(role_delta, 3),
            "weight_multiplier": round(role_multiplier, 3),
            "effect_before": original_effect,
            "effect_after": adjusted_effect,
            "inverted": adjusted_effect != original_effect,
        },
    }


def _planet_strength_percentage(planet_id: str, planet_payload: Dict[str, Any]) -> float:
    target = _PLANET_STRENGTH_TARGETS.get(str(planet_id).strip().lower(), 300.0)
    total_virupas = _safe_float(planet_payload.get("total", 0.0))
    if target <= 0:
        return 0.0
    return max(0.0, min(100.0, (total_virupas / target) * 75.0))


def _resolve_strength_context(strength_payload: Dict[str, Any] | None) -> Dict[str, Any] | None:
    if not isinstance(strength_payload, dict) or not strength_payload:
        return None

    per_planet_scores: Dict[str, float] = {}
    for planet_id, payload in strength_payload.items():
        if not isinstance(payload, dict):
            continue
        normalized_planet = str(planet_id).strip().lower()
        if not normalized_planet:
            continue
        per_planet_scores[normalized_planet] = round(
            _planet_strength_percentage(normalized_planet, payload),
            2,
        )

    if not per_planet_scores:
        return None

    chart_strength_score = round(
        sum(per_planet_scores.values()) / float(len(per_planet_scores)),
        2,
    )
    if chart_strength_score >= _STRONG_OUTCOME_MIN_STRENGTH:
        chart_strength_level = "strong"
    elif chart_strength_score >= _MEDIUM_OUTCOME_MIN_STRENGTH:
        chart_strength_level = "medium"
    else:
        chart_strength_level = "weak"

    return {
        "chart_strength_score": chart_strength_score,
        "chart_strength_level": chart_strength_level,
        "per_planet_scores": per_planet_scores,
    }


def _normalize_identifier(text: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text or "").strip().lower()).strip("_")


def _looks_like_rare_yoga(identifier: Any) -> bool:
    normalized = _normalize_identifier(identifier)
    if not normalized:
        return False
    if "rare_yoga" in normalized:
        return True
    if "yoga" not in normalized:
        return False
    return any(marker in normalized for marker in _RARE_YOGA_MARKERS)


def _collect_strength_override_reasons(bucket: Dict[str, Any]) -> List[str]:
    reasons: List[str] = []

    if bucket.get("allow_strength_override"):
        reasons.append("explicit_override")

    positive_keys = bucket.get("positive_keys", [])
    positive_texts = bucket.get("positive_texts", [])
    if any(_looks_like_rare_yoga(key) for key in positive_keys) or any(
        _looks_like_rare_yoga(text) for text in positive_texts
    ):
        reasons.append("rare_yoga")

    high_confidence_hits = sum(
        1
        for conf in bucket.get("positive_rule_confidences", [])
        if _normalize_confidence_label(conf) == "high"
    )
    reinforcing_signal_count = max(
        len(_deduplicate_values(positive_keys)),
        len(_deduplicate_sentences(positive_texts)),
    )
    if (
        reinforcing_signal_count >= _REINFORCING_COMBO_MIN_RULES
        and _safe_float(bucket.get("positive_score", 0.0)) >= _REINFORCING_COMBO_MIN_SCORE
        and high_confidence_hits >= 2
    ):
        reasons.append("reinforcing_combinations")

    return reasons


def _append_strength_gate_note(summary: str, note: str) -> str:
    base = str(summary or "").strip()
    clean_note = str(note or "").strip()
    if not clean_note:
        return base
    if not base:
        return clean_note
    if clean_note.lower() in base.lower():
        return base
    separator = "" if base.endswith((".", "!", "?")) else "."
    return f"{base}{separator} {clean_note}"


def _gate_note(
    final_confidence: str,
    original_confidence: str,
    strength_context: Dict[str, Any] | None,
) -> str:
    if not strength_context:
        return (
            f"Strength gate lowered confidence from {original_confidence} to {final_confidence} "
            f"because planetary strength data is unavailable."
        )

    return (
        f"Strength gate lowered confidence from {original_confidence} to {final_confidence} "
        f"because chart strength is {strength_context['chart_strength_level']} "
        f"({strength_context['chart_strength_score']}/100)."
    )


def _apply_strength_gate(
    scored_output: Dict[str, Dict[str, Any]],
    grouped: Dict[str, Dict[str, Any]],
    *,
    strength_payload: Dict[str, Any] | None,
) -> None:
    strength_context = _resolve_strength_context(strength_payload)

    for category, details in scored_output.items():
        bucket = grouped.get(category, {})
        original_confidence = _normalize_confidence_label(details.get("confidence", "low"))
        final_confidence = original_confidence
        override_reasons = _collect_strength_override_reasons(bucket)

        gate_status = "not_applicable"
        if original_confidence in {"high", "medium"}:
            gate_status = "passed"
            if override_reasons:
                gate_status = "override"
            elif not strength_context:
                final_confidence = "medium" if original_confidence == "high" else "low"
                gate_status = "downgraded"
            else:
                score = _safe_float(strength_context.get("chart_strength_score"))
                if original_confidence == "high" and score < _STRONG_OUTCOME_MIN_STRENGTH:
                    final_confidence = "medium" if score >= _MEDIUM_OUTCOME_MIN_STRENGTH else "low"
                    gate_status = "downgraded"
                elif original_confidence == "medium" and score < _MEDIUM_OUTCOME_MIN_STRENGTH:
                    final_confidence = "low"
                    gate_status = "downgraded"

        if _CONFIDENCE_ORDER.get(final_confidence, 0) < _CONFIDENCE_ORDER.get(original_confidence, 0):
            details["confidence"] = final_confidence
            details["summary"] = _append_strength_gate_note(
                str(details.get("summary", "")),
                _gate_note(final_confidence, original_confidence, strength_context),
            )

        details["strength_gate"] = {
            "status": gate_status,
            "original_confidence": original_confidence,
            "final_confidence": _normalize_confidence_label(details.get("confidence", original_confidence)),
            "chart_strength_score": (
                strength_context.get("chart_strength_score")
                if strength_context
                else None
            ),
            "chart_strength_level": (
                strength_context.get("chart_strength_level")
                if strength_context
                else "unknown"
            ),
            "strong_threshold": _STRONG_OUTCOME_MIN_STRENGTH,
            "medium_threshold": _MEDIUM_OUTCOME_MIN_STRENGTH,
            "override_applied": bool(override_reasons),
            "override_reasons": _deduplicate_values(override_reasons),
        }


def score_predictions(predictions: list, *, strength_payload: Dict[str, Any] | None = None) -> dict:
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

        role_impact = _apply_functional_role_impact(normalized)
        normalized["effect"] = role_impact["effect"]
        normalized["weight"] = role_impact["weight"]
        normalized["trace"].extend(role_impact["trace_lines"])

        category = normalized["category"]
        bucket = grouped.setdefault(
            category,
            {
                "positive_score": 0.0,
                "negative_score": 0.0,
                "positive_texts": [],
                "negative_texts": [],
                "positive_keys": [],
                "negative_keys": [],
                "trace_lines": [],
                "positive_rule_confidences": [],
                "negative_rule_confidences": [],
                "allow_strength_override": False,
                "functional_notes": [],
                "functional_impacts": [],
                "karaka_notes": [],
                "karaka_modifiers": [],
                "karaka_details": [],
            },
        )

        karaka_modifier = _clamp_karaka_modifier(normalized.get("karaka_modifier", 1.0))
        if normalized["effect"] == "negative":
            # Weak/afflicted karaka should not soften negative outcomes.
            applied_modifier = round(2.0 - karaka_modifier, 6)
        else:
            applied_modifier = karaka_modifier
        normalized["weight"] = round(normalized["weight"] * applied_modifier, 4)
        normalized["trace"].append(
            f"Karaka moderation applied: source={normalized.get('karaka_source', 'neutral')}, "
            f"modifier={karaka_modifier:.3f}, applied_weight_multiplier={applied_modifier:.3f}."
        )
        if isinstance(normalized.get("karaka_impact"), list):
            normalized["trace"].extend(
                str(line).strip() for line in normalized.get("karaka_impact", []) if str(line).strip()
            )
            bucket["karaka_notes"].extend(
                str(line).strip() for line in normalized.get("karaka_impact", []) if str(line).strip()
            )
        if isinstance(normalized.get("karaka_details"), list):
            bucket["karaka_details"].extend(
                detail for detail in normalized.get("karaka_details", []) if isinstance(detail, dict)
            )
        bucket["karaka_modifiers"].append(round(karaka_modifier, 3))

        if normalized["effect"] == "negative":
            bucket["negative_score"] += normalized["weight"]
            bucket["negative_texts"].append(normalized["text"])
            bucket["negative_rule_confidences"].append(normalized["rule_confidence"])
            if normalized["result_key"]:
                bucket["negative_keys"].append(normalized["result_key"])
        else:
            bucket["positive_score"] += normalized["weight"]
            bucket["positive_texts"].append(normalized["text"])
            bucket["positive_rule_confidences"].append(normalized["rule_confidence"])
            if normalized["result_key"]:
                bucket["positive_keys"].append(normalized["result_key"])
            if normalized["allow_strength_override"]:
                bucket["allow_strength_override"] = True

        if role_impact["summary_note"]:
            bucket["functional_notes"].append(role_impact["summary_note"])
        if role_impact["impact"] is not None:
            bucket["functional_impacts"].append(role_impact["impact"])

        bucket["trace_lines"].extend(normalized.get("trace", []))

    scored_output: Dict[str, Dict[str, Any]] = {}
    for category, bucket in grouped.items():
        positive_score = round(bucket["positive_score"], 2)
        negative_score = round(bucket["negative_score"], 2)
        score = round(positive_score - negative_score, 2)
        effect = "positive" if score > 0 else "negative" if score < 0 else "neutral"
        summary = _merge_conflicting_texts(
            bucket["positive_texts"],
            bucket["negative_texts"],
            score,
        )
        functional_note = _merge_texts(bucket.get("functional_notes", []))
        if functional_note:
            summary = _append_strength_gate_note(summary, functional_note)
        karaka_note = _merge_texts(bucket.get("karaka_notes", []))
        if karaka_note:
            summary = _append_strength_gate_note(summary, karaka_note)

        karaka_modifiers = [float(value) for value in bucket.get("karaka_modifiers", []) if _safe_float(value) > 0.0]
        if karaka_modifiers:
            average_karaka_modifier = round(sum(karaka_modifiers) / len(karaka_modifiers), 3)
        else:
            average_karaka_modifier = 1.0

        scored_output[category] = {
            "score": score,
            "confidence": _confidence_from_score(score),
            "effect": effect,
            "positive_score": positive_score,
            "negative_score": negative_score,
            "summary": summary,
            "positive_summary_keys": _deduplicate_values(bucket["positive_keys"]),
            "negative_summary_keys": _deduplicate_values(bucket["negative_keys"]),
            "trace": _deduplicate_values(bucket["trace_lines"]),
            "functional_role_notes": _deduplicate_values(bucket.get("functional_notes", [])),
            "functional_impacts": list(bucket.get("functional_impacts", [])),
            "karaka_modifier": average_karaka_modifier,
            "karaka_impact": _deduplicate_values(bucket.get("karaka_notes", [])),
            "karaka_details": list(bucket.get("karaka_details", [])),
        }

    _apply_strength_gate(
        scored_output,
        grouped,
        strength_payload=strength_payload,
    )

    return scored_output
