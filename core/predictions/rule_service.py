from __future__ import annotations

import json
from pathlib import Path
from string import Formatter
from typing import Any, Dict, Mapping

from app.utils.runtime_paths import resolve_resource

from .prediction_service import (
    get_conflict_resolution_priority,
    get_conflict_resolution_thresholds,
)


_DEFAULT_LANGUAGE = "en"
_SUPPORTED_LANGUAGES = {"en", "hi", "or"}
_TRANSLATION_CACHE: dict[str, dict[str, Any]] = {}
_TRANSLATIONS_DIR = Path(resolve_resource("app", "data", "translations"))
_PARASHARI_REQUIRED_KEYS: tuple[str, ...] = (
    "prediction.parashari.labels.promise",
    "prediction.parashari.labels.strength",
    "prediction.parashari.labels.timing",
    "prediction.parashari.labels.caution",
    "prediction.parashari.areas.general",
    "prediction.parashari.promise.with_yoga",
    "prediction.parashari.promise.without_yoga",
    "prediction.parashari.promise.lordship_supportive",
    "prediction.parashari.promise.lordship_mixed",
    "prediction.parashari.promise.lordship_neutral",
    "prediction.parashari.strength.strong_indication",
    "prediction.parashari.strength.moderate_strength",
    "prediction.parashari.strength.weak_influence",
    "prediction.parashari.strength.varga_clause",
    "prediction.parashari.strength.composed",
    "prediction.parashari.timing.currently_active",
    "prediction.parashari.timing.upcoming_period",
    "prediction.parashari.timing.dormant_phase",
    "prediction.parashari.timing.transit_amplifying",
    "prediction.parashari.timing.transit_suppressing",
    "prediction.parashari.timing.transit_neutral",
    "prediction.parashari.timing.composed",
    "prediction.parashari.conflict.despite_conflicting_indications",
    "prediction.parashari.conflict.dominant_factor",
    "prediction.parashari.conflict.suppressed_influence",
    "prediction.parashari.conflict.balanced",
    "prediction.parashari.karaka.natural_significator_supports",
    "prediction.parashari.karaka.afflicted_karaka_reduces_outcome",
    "prediction.parashari.karaka.neutral_karaka",
    "prediction.parashari.caution.reason_clause",
    "prediction.parashari.caution.reason_fallback",
    "prediction.parashari.caution.composed",
    "prediction.parashari.fallback.section_unavailable",
    "prediction.parashari.fallback.narrative_unavailable",
)


def resolve_conflicts(signals: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Deterministically resolves conflicting astrological indications.

    Priority hierarchy (high -> low):
    1) Strength Gate
    2) Dasha Activation
    3) House-lord condition
    4) Yoga status
    5) Varga concordance
    6) Transit trigger
    """
    payload = dict(signals or {})
    language = _normalize_language(payload.get("language", payload.get("lang", _DEFAULT_LANGUAGE)))
    priority = get_conflict_resolution_priority()
    thresholds = get_conflict_resolution_thresholds()

    strength = _normalize_strength(payload.get("strength_gate"), thresholds)
    dasha = _normalize_dasha(payload.get("dasha_activation"), thresholds)
    house_lord = _normalize_house_lord(payload.get("house_lord_condition"), thresholds)
    yoga = _normalize_yoga(payload.get("yoga_status"))
    varga = _normalize_varga(payload.get("varga_concordance"), thresholds)
    transit = _normalize_transit(payload.get("transit_trigger"))

    rationale: list[str] = []
    suppressed: list[dict[str, str]] = []
    supporting_factors: list[str] = []
    conflicting_factors: list[str] = []
    dominant_outcome = "valid"
    dominant_factor = "dasha_activation"
    dominant_reason_key = "prediction.conflict.reasons.balanced_layers"
    score_multiplier = 1.0
    confidence_multiplier = 1.0

    if not strength["passed"]:
        dominant_outcome = "suppressed"
        dominant_factor = "strength_gate"
        dominant_reason_key = "prediction.conflict.reasons.strength_gate_failed"
        rationale.append(_t(language, "prediction.conflict.rationale.strength_failed"))
        score_multiplier = 0.0
        conflicting_factors.extend(
            [
                "strength_gate",
                "dasha_activation",
                "house_lord_condition",
                "yoga_status",
                "varga_concordance",
                "transit_trigger",
            ]
        )
        suppressed.extend(
            [
                _suppressed("dasha_activation", _t(language, "prediction.conflict.suppression_reasons.hard_filter_strength")),
                _suppressed("house_lord_condition", _t(language, "prediction.conflict.suppression_reasons.hard_filter_strength")),
                _suppressed("yoga_status", _t(language, "prediction.conflict.suppression_reasons.hard_filter_strength")),
                _suppressed("varga_concordance", _t(language, "prediction.conflict.suppression_reasons.hard_filter_strength")),
                _suppressed("transit_trigger", _t(language, "prediction.conflict.suppression_reasons.hard_filter_strength")),
            ]
        )
        return _build_resolution_payload(
            dominant_outcome=dominant_outcome,
            suppressed=suppressed,
            rationale=rationale,
            priority=priority,
            score_multiplier=score_multiplier,
            confidence_multiplier=confidence_multiplier,
            language=language,
            dominant_factor=dominant_factor,
            dominant_reason_key=dominant_reason_key,
            supporting_factors=supporting_factors,
            conflicting_factors=conflicting_factors,
        )

    supporting_factors.append("strength_gate")
    rationale.append(_t(language, "prediction.conflict.rationale.strength_passed"))

    if not dasha["active"]:
        dominant_outcome = "suppressed"
        dominant_factor = "dasha_activation"
        dominant_reason_key = "prediction.conflict.reasons.dasha_inactive"
        conflicting_factors.extend(
            [
                "dasha_activation",
                "house_lord_condition",
                "yoga_status",
                "varga_concordance",
                "transit_trigger",
            ]
        )
        rationale.append(_t(language, "prediction.conflict.rationale.dasha_inactive"))
        score_multiplier = 0.0
        suppressed.extend(
            [
                _suppressed("house_lord_condition", _t(language, "prediction.conflict.suppression_reasons.inactive_dasha_timing")),
                _suppressed("yoga_status", _t(language, "prediction.conflict.suppression_reasons.inactive_dasha_timing")),
                _suppressed("varga_concordance", _t(language, "prediction.conflict.suppression_reasons.inactive_dasha_timing")),
                _suppressed("transit_trigger", _t(language, "prediction.conflict.suppression_reasons.inactive_dasha_timing")),
            ]
        )
        return _build_resolution_payload(
            dominant_outcome=dominant_outcome,
            suppressed=suppressed,
            rationale=rationale,
            priority=priority,
            score_multiplier=score_multiplier,
            confidence_multiplier=confidence_multiplier,
            language=language,
            dominant_factor=dominant_factor,
            dominant_reason_key=dominant_reason_key,
            supporting_factors=supporting_factors,
            conflicting_factors=conflicting_factors,
        )

    supporting_factors.append("dasha_activation")
    rationale.append(_t(language, "prediction.conflict.rationale.dasha_active"))

    if house_lord["state"] == "weak":
        dominant_outcome = "tempered"
        dominant_factor = "house_lord_condition"
        dominant_reason_key = "prediction.conflict.reasons.house_lord_weak"
        conflicting_factors.append("house_lord_condition")
        rationale.append(_t(language, "prediction.conflict.rationale.house_lord_weak"))
        score_multiplier *= house_lord["weak_multiplier"]
        suppressed.append(
            _suppressed(
                "yoga_status",
                _t(language, "prediction.conflict.suppression_reasons.house_lord_over_yoga"),
            )
        )
    elif house_lord["state"] == "strong":
        supporting_factors.append("house_lord_condition")
        rationale.append(_t(language, "prediction.conflict.rationale.house_lord_strong"))
    else:
        rationale.append(_t(language, "prediction.conflict.rationale.house_lord_neutral"))

    if yoga["cancelled"]:
        dominant_outcome = "suppressed"
        dominant_factor = "yoga_status"
        dominant_reason_key = "prediction.conflict.reasons.yoga_cancelled"
        conflicting_factors.append("yoga_status")
        rationale.append(_t(language, "prediction.conflict.rationale.yoga_cancelled"))
        score_multiplier = 0.0
        suppressed.append(
            _suppressed("yoga_status", _t(language, "prediction.conflict.suppression_reasons.yoga_cancelled_no_domination"))
        )
        suppressed.append(
            _suppressed("transit_trigger", _t(language, "prediction.conflict.suppression_reasons.transit_cannot_revive_cancelled_yoga"))
        )
        conflicting_factors.append("transit_trigger")
        return _build_resolution_payload(
            dominant_outcome=dominant_outcome,
            suppressed=suppressed,
            rationale=rationale,
            priority=priority,
            score_multiplier=score_multiplier,
            confidence_multiplier=confidence_multiplier,
            language=language,
            dominant_factor=dominant_factor,
            dominant_reason_key=dominant_reason_key,
            supporting_factors=supporting_factors,
            conflicting_factors=conflicting_factors,
        )
    if yoga["state"] == "strong":
        supporting_factors.append("yoga_status")
        rationale.append(_t(language, "prediction.conflict.rationale.yoga_supportive"))
    elif yoga["state"] == "weak":
        conflicting_factors.append("yoga_status")
        rationale.append(_t(language, "prediction.conflict.rationale.yoga_weak_secondary"))

    if varga["conflicting"]:
        confidence_multiplier *= varga["confidence_multiplier"]
        score_multiplier *= varga["score_multiplier"]
        conflicting_factors.append("varga_concordance")
        if dominant_outcome == "valid":
            dominant_reason_key = "prediction.conflict.reasons.varga_conflict"
        suppressed.append(
            _suppressed(
                "varga_concordance",
                _t(language, "prediction.conflict.suppression_reasons.varga_conflict_confidence_only"),
            )
        )
        rationale.append(_t(language, "prediction.conflict.rationale.varga_conflict_reduced"))
    else:
        supporting_factors.append("varga_concordance")
        rationale.append(_t(language, "prediction.conflict.rationale.varga_non_conflict"))

    if transit["support_state"] == "suppressing":
        conflicting_factors.append("transit_trigger")
        if strength["state"] == "strong" and dasha["active"]:
            suppressed.append(
                _suppressed(
                    "transit_trigger",
                    _t(language, "prediction.conflict.suppression_reasons.weak_transit_low_priority"),
                )
            )
            rationale.append(_t(language, "prediction.conflict.rationale.transit_weak_non_override"))
        else:
            score_multiplier *= 0.95
            rationale.append(_t(language, "prediction.conflict.rationale.transit_suppressing_mild"))
    elif transit["support_state"] == "amplifying":
        supporting_factors.append("transit_trigger")
        rationale.append(_t(language, "prediction.conflict.rationale.transit_amplifying_secondary"))
    else:
        rationale.append(_t(language, "prediction.conflict.rationale.transit_neutral"))

    if dominant_outcome == "valid" and dominant_reason_key == "prediction.conflict.reasons.balanced_layers":
        rationale.append(_t(language, "prediction.conflict.rationale.balanced_layers"))

    return _build_resolution_payload(
        dominant_outcome=dominant_outcome,
        suppressed=suppressed,
        rationale=rationale,
        priority=priority,
        score_multiplier=score_multiplier,
        confidence_multiplier=confidence_multiplier,
        language=language,
        dominant_factor=dominant_factor,
        dominant_reason_key=dominant_reason_key,
        supporting_factors=supporting_factors,
        conflicting_factors=conflicting_factors,
    )


def compose_parashari_narrative(prediction_context: Mapping[str, Any] | None) -> Dict[str, str]:
    """
    Builds a deterministic Promise -> Strength -> Timing -> Caution narrative.

    Section mapping:
    - Promise: M3 (bhava/lord) + M4 (yoga)
    - Strength: M1 (bala) + M7 (varga concordance) + M10 (karaka)
    - Timing: M5 (dasha) + M6 (transit)
    - Caution: M9 (conflict resolver + suppressed signals)
    """
    context = dict(prediction_context or {})
    language = _normalize_language(context.get("language", context.get("lang", _DEFAULT_LANGUAGE)))
    validation = validate_parashari_localization(language)
    if validation["missing_in_language"] or validation["missing_in_default"]:
        return _compose_parashari_unavailable(language)

    promise_text = _compose_promise_section(context, language)
    strength_text = _compose_strength_section(context, language)
    timing_text = _compose_timing_section(context, language)
    caution_text = _compose_caution_section(context, language)

    ordered_sections = [
        _ensure_sentence(promise_text),
        _ensure_sentence(strength_text),
        _ensure_sentence(timing_text),
        _ensure_sentence(caution_text),
    ]
    final_narrative = " ".join(section for section in ordered_sections if section).strip()

    return {
        "promise_text": ordered_sections[0],
        "strength_text": ordered_sections[1],
        "timing_text": ordered_sections[2],
        "caution_text": ordered_sections[3],
        "final_narrative": final_narrative,
    }


def _compose_promise_section(context: Mapping[str, Any], language: str) -> str:
    area_key = _normalize_area_key(context.get("area"))
    area_label = _resolve_area_label(area_key, language)
    yoga = str(context.get("yoga", "")).strip()
    lordship_score = _safe_float(context.get("lordship_score"), 0.0)

    if lordship_score >= 65.0:
        lordship_state = _t_parashari(language, "prediction.parashari.promise.lordship_supportive")
    elif lordship_score > 0 and lordship_score <= 40.0:
        lordship_state = _t_parashari(language, "prediction.parashari.promise.lordship_mixed")
    else:
        lordship_state = _t_parashari(language, "prediction.parashari.promise.lordship_neutral")

    if yoga:
        core = _format_parashari(
            language,
            "prediction.parashari.promise.with_yoga",
            {
                "area": area_label,
                "yoga": yoga,
                "lordship_state": lordship_state,
            },
        )
    else:
        core = _format_parashari(
            language,
            "prediction.parashari.promise.without_yoga",
            {"area": area_label, "lordship_state": lordship_state},
        )

    label = _t_parashari(language, "prediction.parashari.labels.promise")
    return _compose_labeled_parashari_section(language, label, core)


def _compose_strength_section(context: Mapping[str, Any], language: str) -> str:
    strength_level = str(context.get("strength", "")).strip().lower()
    strength_score = _safe_float(context.get("strength_score"), 0.0)

    if strength_level not in {"strong", "medium", "weak"}:
        if strength_score >= 68.0:
            strength_level = "strong"
        elif strength_score >= 52.0:
            strength_level = "medium"
        else:
            strength_level = "weak"

    if strength_level == "strong":
        strength_expression = _t_parashari(language, "prediction.parashari.strength.strong_indication")
    elif strength_level == "weak":
        strength_expression = _t_parashari(language, "prediction.parashari.strength.weak_influence")
    else:
        strength_expression = _t_parashari(language, "prediction.parashari.strength.moderate_strength")

    agreement_level = str(context.get("agreement_level", "medium")).strip().lower() or "medium"
    if agreement_level not in {"high", "medium", "low"}:
        agreement_level = "medium"
    concordance_score = _safe_float(context.get("concordance_score"), 0.0)
    varga_piece = _format_parashari(
        language,
        "prediction.parashari.strength.varga_clause",
        {"agreement_level": agreement_level, "score": f"{concordance_score:.2f}"},
    )

    karaka_source = str(context.get("karaka_source", "")).strip().lower() or "neutral"
    if karaka_source not in {"supportive", "neutral", "adverse"}:
        karaka_source = "neutral"
    if karaka_source == "supportive":
        karaka_piece = _t_parashari(language, "prediction.parashari.karaka.natural_significator_supports")
    elif karaka_source == "adverse":
        karaka_piece = _t_parashari(language, "prediction.parashari.karaka.afflicted_karaka_reduces_outcome")
    else:
        karaka_piece = _t_parashari(language, "prediction.parashari.karaka.neutral_karaka")

    core = _format_parashari(
        language,
        "prediction.parashari.strength.composed",
        {
            "strength_expression": strength_expression,
            "varga_clause": varga_piece,
            "karaka_clause": karaka_piece,
        },
    )

    label = _t_parashari(language, "prediction.parashari.labels.strength")
    return _compose_labeled_parashari_section(language, label, core)


def _compose_timing_section(context: Mapping[str, Any], language: str) -> str:
    timing = context.get("timing", {})
    if not isinstance(timing, Mapping):
        timing = {}

    mahadasha = str(timing.get("mahadasha", "")).strip()
    antardasha = str(timing.get("antardasha", "")).strip()
    relevance = str(timing.get("activation_level", timing.get("relevance", "low"))).strip().lower() or "low"

    if relevance not in {"high", "medium", "low"}:
        relevance = "low"

    transit = context.get("transit", {})
    if not isinstance(transit, Mapping):
        transit = {}
    transit_state = str(transit.get("support_state", "neutral")).strip().lower() or "neutral"

    if (mahadasha or antardasha) and relevance == "high":
        timing_expression = _t_parashari(language, "prediction.parashari.timing.currently_active")
    elif (mahadasha or antardasha) and relevance == "medium":
        timing_expression = _t_parashari(language, "prediction.parashari.timing.upcoming_period")
    else:
        timing_expression = _t_parashari(language, "prediction.parashari.timing.dormant_phase")

    if transit_state == "amplifying":
        transit_piece = _t_parashari(language, "prediction.parashari.timing.transit_amplifying")
    elif transit_state == "suppressing":
        transit_piece = _t_parashari(language, "prediction.parashari.timing.transit_suppressing")
    else:
        transit_piece = _t_parashari(language, "prediction.parashari.timing.transit_neutral")

    core = _format_parashari(
        language,
        "prediction.parashari.timing.composed",
        {"timing_expression": timing_expression, "transit_clause": transit_piece},
    )
    label = _t_parashari(language, "prediction.parashari.labels.timing")
    return _compose_labeled_parashari_section(language, label, core)


def _compose_caution_section(context: Mapping[str, Any], language: str) -> str:
    resolution = context.get("resolution", {})
    if not isinstance(resolution, Mapping):
        resolution = {}

    dominant_outcome = str(
        resolution.get("dominant_outcome", context.get("dominant_outcome", "valid"))
    ).strip().lower() or "valid"
    dominant_reason = str(
        resolution.get("dominant_reasoning", context.get("dominant_reasoning", ""))
    ).strip()
    explanation = str(
        resolution.get("resolution_explanation", context.get("resolution_explanation", ""))
    ).strip()

    suppressed = resolution.get("suppressed_factors", context.get("suppressed_factors", []))
    suppressed_labels: list[str] = []
    if isinstance(suppressed, list):
        for row in suppressed:
            factor_key = ""
            if isinstance(row, Mapping):
                factor_key = str(row.get("factor", "")).strip()
            else:
                factor_key = str(row or "").strip()
            if not factor_key:
                continue
            label = _factor_label(language, factor_key)
            if label and label not in suppressed_labels:
                suppressed_labels.append(label)

    if dominant_outcome in {"suppressed", "tempered"}:
        outcome_clause = _t_parashari(language, "prediction.parashari.conflict.despite_conflicting_indications")
    else:
        outcome_clause = _t_parashari(language, "prediction.parashari.conflict.balanced")

    dominant_factor_key = str(resolution.get("dominant_factor", context.get("dominant_factor", ""))).strip()
    dominant_factor_label = _factor_label(language, dominant_factor_key) if dominant_factor_key else ""
    dominant_clause = (
        _format_parashari(
            language,
            "prediction.parashari.conflict.dominant_factor",
            {"dominant_factor": dominant_factor_label},
        )
        if dominant_factor_label
        else ""
    )

    if suppressed_labels:
        suppressed_clause = _format_parashari(
            language,
            "prediction.parashari.conflict.suppressed_influence",
            {"suppressed": ", ".join(suppressed_labels)},
        )
    else:
        suppressed_clause = ""

    reason_text = dominant_reason or explanation
    if reason_text:
        reason_clause = _format_parashari(
            language,
            "prediction.parashari.caution.reason_clause",
            {"reason": reason_text},
        )
    else:
        reason_clause = _t_parashari(language, "prediction.parashari.caution.reason_fallback")

    if dominant_clause and dominant_clause.lower() == outcome_clause.lower():
        dominant_clause = ""
    if suppressed_clause and suppressed_clause.lower() in {outcome_clause.lower(), dominant_clause.lower()}:
        suppressed_clause = ""
    if reason_clause and reason_clause.lower() in {
        outcome_clause.lower(),
        dominant_clause.lower(),
        suppressed_clause.lower(),
    }:
        reason_clause = ""

    caution_text = _format_parashari(
        language,
        "prediction.parashari.caution.composed",
        {
            "outcome_clause": outcome_clause,
            "dominant_clause": dominant_clause,
            "suppressed_clause": suppressed_clause,
            "reason_clause": reason_clause,
        },
    )
    if not caution_text:
        caution_text = "; ".join(
            _dedupe_text([outcome_clause, dominant_clause, suppressed_clause, reason_clause])
        )

    label = _t_parashari(language, "prediction.parashari.labels.caution")
    return _compose_labeled_parashari_section(language, label, caution_text)


def _normalize_area_key(raw_area: Any) -> str:
    area = str(raw_area or "general").strip().lower() or "general"
    aliases = {"wealth": "finance", "financial": "finance", "loss/spiritual": "general"}
    return aliases.get(area, area)


def _resolve_area_label(area_key: str, language: str) -> str:
    value = _t_parashari(language, f"prediction.parashari.areas.{area_key}")
    if value:
        return value
    return _t_parashari(language, "prediction.parashari.areas.general")


def validate_parashari_localization(language: str) -> Dict[str, list[str]]:
    normalized = _normalize_language(language)
    language_payload = _load_translation_payload(normalized)
    default_payload = _load_translation_payload(_DEFAULT_LANGUAGE)
    missing_in_language: list[str] = []
    missing_in_default: list[str] = []

    for key in _PARASHARI_REQUIRED_KEYS:
        localized = _resolve_key(language_payload, key)
        default = _resolve_key(default_payload, key)
        if default is None or not str(default).strip():
            missing_in_default.append(key)
        if localized is None or not str(localized).strip():
            missing_in_language.append(key)

    return {
        "missing_in_language": sorted(set(missing_in_language)),
        "missing_in_default": sorted(set(missing_in_default)),
    }


def _compose_parashari_unavailable(language: str) -> Dict[str, str]:
    section_text = _t_parashari(language, "prediction.parashari.fallback.section_unavailable")
    narrative_text = _t_parashari(language, "prediction.parashari.fallback.narrative_unavailable")
    promise = _compose_labeled_parashari_section(
        language,
        _t_parashari(language, "prediction.parashari.labels.promise"),
        section_text,
    )
    strength = _compose_labeled_parashari_section(
        language,
        _t_parashari(language, "prediction.parashari.labels.strength"),
        section_text,
    )
    timing = _compose_labeled_parashari_section(
        language,
        _t_parashari(language, "prediction.parashari.labels.timing"),
        section_text,
    )
    caution = _compose_labeled_parashari_section(
        language,
        _t_parashari(language, "prediction.parashari.labels.caution"),
        section_text,
    )
    final_narrative = _ensure_sentence(narrative_text)
    if not final_narrative:
        final_narrative = " ".join(
            part
            for part in (
                _ensure_sentence(promise),
                _ensure_sentence(strength),
                _ensure_sentence(timing),
                _ensure_sentence(caution),
            )
            if part
        ).strip()
    return {
        "promise_text": _ensure_sentence(promise),
        "strength_text": _ensure_sentence(strength),
        "timing_text": _ensure_sentence(timing),
        "caution_text": _ensure_sentence(caution),
        "final_narrative": final_narrative,
    }


def _compose_labeled_parashari_section(language: str, label: str, content: str) -> str:
    safe_content = str(content or "").strip()
    if not safe_content:
        safe_content = _t_parashari(language, "prediction.parashari.fallback.section_unavailable")
    safe_label = str(label or "").strip()
    if safe_label and safe_content:
        return f"{safe_label}: {safe_content}"
    return safe_label or safe_content


def _t_parashari(language: str, key: str) -> str:
    value = _resolve_localized_value(language, key, include_default=True)
    if value is None:
        return ""
    return str(value).strip()


def _format_parashari(language: str, key: str, params: Mapping[str, Any]) -> str:
    template = _t_parashari(language, key)
    if not template:
        return ""

    required_fields = {
        field_name
        for _, field_name, _, _ in Formatter().parse(template)
        if field_name and field_name.isidentifier()
    }
    safe_params = {str(k): str(v) for k, v in dict(params or {}).items() if v is not None}
    if any(field not in safe_params for field in required_fields):
        return ""

    try:
        rendered = template.format_map(_SafeFormatDict(safe_params)).strip()
    except (ValueError, KeyError):
        return ""

    unresolved_fields = {
        field_name
        for _, field_name, _, _ in Formatter().parse(rendered)
        if field_name and field_name.isidentifier()
    }
    if unresolved_fields:
        return ""

    return _clean_parashari_composed_text(rendered)


def _clean_parashari_composed_text(text: str) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    if ";" not in value:
        return " ".join(value.split())
    segments = [part.strip().strip(".,;") for part in value.split(";")]
    clean_segments = [segment for segment in segments if segment]
    return "; ".join(clean_segments)


def _ensure_sentence(text: str) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    if value.endswith((".", "!", "?")):
        return value
    return value + "."


def _normalize_strength(raw: Any, thresholds: Mapping[str, Any]) -> Dict[str, Any]:
    score = _safe_float(_read(raw, "score"), 0.0)
    strong_cutoff = _safe_float(thresholds.get("strength_strong_score"), 68.0)
    pass_cutoff = _safe_float(thresholds.get("strength_min_score"), 52.0)

    if score >= strong_cutoff:
        state = "strong"
    elif score >= pass_cutoff:
        state = "medium"
    else:
        state = "weak"

    return {
        "score": round(score, 3),
        "state": state,
        "passed": score >= pass_cutoff,
    }


def _normalize_dasha(raw: Any, thresholds: Mapping[str, Any]) -> Dict[str, Any]:
    level = str(_read(raw, "level", _read(raw, "activation_level", "low"))).strip().lower() or "low"
    multiplier = _safe_float(_read(raw, "multiplier"), 1.0)
    active_cutoff = _safe_float(thresholds.get("dasha_active_multiplier_min"), 0.98)

    active = level in {"medium", "high"} and multiplier >= active_cutoff
    return {
        "level": level,
        "multiplier": round(multiplier, 3),
        "active": active,
    }


def _normalize_house_lord(raw: Any, thresholds: Mapping[str, Any]) -> Dict[str, Any]:
    score = _safe_float(_read(raw, "score"), 50.0)
    strong_cutoff = _safe_float(thresholds.get("lordship_strong_score"), 65.0)
    weak_cutoff = _safe_float(thresholds.get("lordship_weak_score"), 40.0)
    weak_multiplier = _safe_float(thresholds.get("lordship_weak_multiplier"), 0.7)

    if score >= strong_cutoff:
        state = "strong"
    elif score <= weak_cutoff:
        state = "weak"
    else:
        state = "neutral"

    return {
        "score": round(score, 3),
        "state": state,
        "weak_multiplier": max(0.0, min(1.0, weak_multiplier)),
    }


def _normalize_yoga(raw: Any) -> Dict[str, Any]:
    state = str(_read(raw, "state", "neutral")).strip().lower() or "neutral"
    is_cancelled = bool(_read(raw, "is_cancelled", False)) or state in {"cancelled", "bhanga"}
    if state in {"strong", "formed", "active"}:
        mapped_state = "strong"
    elif state in {"weak"}:
        mapped_state = "weak"
    elif is_cancelled:
        mapped_state = "cancelled"
    else:
        mapped_state = "neutral"

    return {
        "state": mapped_state,
        "cancelled": is_cancelled,
    }


def _normalize_varga(raw: Any, thresholds: Mapping[str, Any]) -> Dict[str, Any]:
    agreement = str(_read(raw, "agreement_level", "medium")).strip().lower() or "medium"
    score = _safe_float(_read(raw, "score"), 0.5)
    conflict_cutoff = _safe_float(thresholds.get("varga_conflict_score_max"), 0.4)
    conflicting = agreement == "low" or score < conflict_cutoff

    return {
        "agreement_level": agreement,
        "score": round(score, 3),
        "conflicting": conflicting,
        "confidence_multiplier": _safe_float(
            thresholds.get("varga_conflict_confidence_multiplier"),
            0.72,
        ),
        "score_multiplier": _safe_float(
            thresholds.get("varga_conflict_score_multiplier"),
            0.92,
        ),
    }


def _normalize_transit(raw: Any) -> Dict[str, Any]:
    support_state = str(_read(raw, "support_state", "neutral")).strip().lower() or "neutral"
    trigger_level = str(_read(raw, "trigger_level", "low")).strip().lower() or "low"
    return {
        "support_state": support_state,
        "trigger_level": trigger_level,
    }


def _build_resolution_payload(
    *,
    dominant_outcome: str,
    suppressed: list[dict[str, str]],
    rationale: list[str],
    priority: list[str],
    score_multiplier: float,
    confidence_multiplier: float,
    language: str,
    dominant_factor: str,
    dominant_reason_key: str,
    supporting_factors: list[str],
    conflicting_factors: list[str],
) -> Dict[str, Any]:
    cleaned_rationale = _dedupe_text(rationale)
    suppressed_rows = _dedupe_suppressed(suppressed)
    narrative = _build_contradiction_narrative(
        language=language,
        dominant_outcome=dominant_outcome,
        dominant_factor=dominant_factor,
        dominant_reason_key=dominant_reason_key,
        supporting_factors=supporting_factors,
        conflicting_factors=conflicting_factors,
    )
    dominant_reasoning = str(narrative.get("primary_conclusion", "")).strip()
    explanation = str(narrative.get("resolution_explanation", "")).strip()

    return {
        "dominant_outcome": dominant_outcome,
        "suppressed_factors": suppressed_rows,
        "rationale": cleaned_rationale,
        "dominant_reasoning": dominant_reasoning,
        "resolution_explanation": explanation,
        "primary_conclusion": dominant_reasoning,
        "supporting_factors": narrative.get("supporting_factors", ""),
        "conflicting_factors": narrative.get("conflicting_factors", ""),
        "narrative": narrative,
        "language": language,
        "priority_order": list(priority),
        "score_multiplier": round(max(0.0, score_multiplier), 6),
        "confidence_multiplier": round(max(0.0, confidence_multiplier), 6),
    }


def _suppressed(name: str, reason: str) -> dict[str, str]:
    return {"factor": str(name).strip(), "reason": str(reason).strip()}


def _dedupe_text(rows: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for row in rows:
        text = str(row or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        output.append(text)
    return output


def _dedupe_suppressed(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        factor = str(row.get("factor", "")).strip()
        reason = str(row.get("reason", "")).strip()
        if not factor:
            continue
        key = (factor.lower(), reason.lower())
        if key in seen:
            continue
        seen.add(key)
        output.append({"factor": factor, "reason": reason})
    return output


def _read(payload: Any, key: str, default: Any = None) -> Any:
    if isinstance(payload, Mapping):
        return payload.get(key, default)
    return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_language(language: Any) -> str:
    normalized = str(language or _DEFAULT_LANGUAGE).strip().lower() or _DEFAULT_LANGUAGE
    if normalized not in _SUPPORTED_LANGUAGES:
        return _DEFAULT_LANGUAGE
    return normalized


def _load_translation_payload(language: str) -> dict[str, Any]:
    normalized = _normalize_language(language)
    cached = _TRANSLATION_CACHE.get(normalized)
    if cached is not None:
        return cached

    file_path = _TRANSLATIONS_DIR / f"{normalized}.json"
    payload: dict[str, Any] = {}
    try:
        if file_path.exists():
            loaded = json.loads(file_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                payload = loaded
    except (OSError, json.JSONDecodeError):
        payload = {}

    _TRANSLATION_CACHE[normalized] = payload
    return payload


def _resolve_key(payload: Mapping[str, Any], key: str) -> str | None:
    current: Any = payload
    for part in str(key or "").split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    if current is None:
        return None
    return str(current)


def _resolve_localized_value(language: str, key: str, *, include_default: bool = True) -> str | None:
    ordered_languages = [_normalize_language(language)]
    if include_default and _DEFAULT_LANGUAGE not in ordered_languages:
        ordered_languages.append(_DEFAULT_LANGUAGE)
    for lang in ordered_languages:
        payload = _load_translation_payload(lang)
        resolved = _resolve_key(payload, key)
        if resolved is not None and str(resolved).strip():
            return str(resolved)
    return None


def _t(language: str, key: str) -> str:
    for lang in (_normalize_language(language), _DEFAULT_LANGUAGE):
        payload = _load_translation_payload(lang)
        resolved = _resolve_key(payload, key)
        if resolved is not None and resolved != "":
            return resolved
    return key


class _SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + str(key) + "}"


def _format_t(language: str, key: str, params: Mapping[str, Any]) -> str:
    template = _t(language, key)
    safe_params = _SafeFormatDict({k: str(v) for k, v in dict(params or {}).items()})
    try:
        return template.format_map(safe_params)
    except (ValueError, KeyError):
        return template


def _factor_label(language: str, factor_key: str) -> str:
    text = _t(language, f"prediction.conflict.factor_labels.{factor_key}")
    if text.startswith("prediction.conflict.factor_labels."):
        return str(factor_key).replace("_", " ").strip()
    return text


def _join_factor_labels(factor_keys: list[str], language: str, *, fallback_key: str) -> str:
    labels = _dedupe_text([_factor_label(language, key) for key in factor_keys])
    if not labels:
        return _t(language, fallback_key)
    return ", ".join(labels)


def _build_contradiction_narrative(
    *,
    language: str,
    dominant_outcome: str,
    dominant_factor: str,
    dominant_reason_key: str,
    supporting_factors: list[str],
    conflicting_factors: list[str],
) -> Dict[str, Any]:
    positive_factor = _join_factor_labels(
        supporting_factors,
        language,
        fallback_key="prediction.conflict.fallback.none_supporting",
    )
    negative_factor = _join_factor_labels(
        conflicting_factors,
        language,
        fallback_key="prediction.conflict.fallback.none_conflicting",
    )
    dominant_factor_text = _factor_label(language, dominant_factor)
    reason_text = _t(language, dominant_reason_key)
    final_conclusion = _t(language, f"prediction.conflict.outcomes.{dominant_outcome}")
    if final_conclusion.startswith("prediction.conflict.outcomes."):
        final_conclusion = dominant_outcome

    params = {
        "positive_factor": positive_factor,
        "negative_factor": negative_factor,
        "dominant_factor": dominant_factor_text,
        "reason": reason_text,
        "final_conclusion": final_conclusion,
    }

    if dominant_outcome == "suppressed" and positive_factor != _t(language, "prediction.conflict.fallback.none_supporting"):
        template_key = "prediction.conflict.templates.suppressed"
    elif (
        positive_factor != _t(language, "prediction.conflict.fallback.none_supporting")
        and negative_factor != _t(language, "prediction.conflict.fallback.none_conflicting")
    ):
        template_key = "prediction.conflict.templates.mixed"
    else:
        template_key = "prediction.conflict.templates.dominant"

    resolution_text = _format_t(language, template_key, params)
    primary = _format_t(language, "prediction.conflict.sections.primary_conclusion", params)
    supporting = _format_t(language, "prediction.conflict.sections.supporting_factors", params)
    conflicting = _format_t(language, "prediction.conflict.sections.conflicting_factors", params)
    resolution = _format_t(
        language,
        "prediction.conflict.sections.resolution_explanation",
        {**params, "resolution_text": resolution_text},
    )

    return {
        "primary_conclusion": primary,
        "supporting_factors": supporting,
        "conflicting_factors": conflicting,
        "resolution_explanation": resolution,
        "template_key": template_key,
        "params": params,
    }
