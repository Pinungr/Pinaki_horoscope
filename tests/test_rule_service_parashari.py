from __future__ import annotations

import json
import string
import unittest
from pathlib import Path
from unittest.mock import patch

from core.predictions.rule_service import compose_parashari_narrative, validate_parashari_localization


class RuleServiceParashariTests(unittest.TestCase):
    def test_compose_parashari_narrative_builds_all_sections(self) -> None:
        payload = compose_parashari_narrative(
            {
                "area": "career",
                "yoga": "Raj Yoga",
                "strength": "strong",
                "strength_score": 81.5,
                "agreement_level": "high",
                "concordance_score": 0.82,
                "karaka_source": "supportive",
                "timing": {
                    "mahadasha": "Jupiter",
                    "antardasha": "Venus",
                    "activation_level": "high",
                },
                "transit": {"support_state": "amplifying"},
                "resolution": {"dominant_outcome": "valid"},
            }
        )

        self.assertTrue(payload["promise_text"].startswith("Promise:"))
        self.assertTrue(payload["strength_text"].startswith("Strength:"))
        self.assertTrue(payload["timing_text"].startswith("Timing:"))
        self.assertTrue(payload["caution_text"].startswith("Caution:"))
        self.assertIn("Promise:", payload["final_narrative"])
        self.assertIn("Strength:", payload["final_narrative"])
        self.assertIn("Timing:", payload["final_narrative"])
        self.assertIn("Caution:", payload["final_narrative"])

    def test_compose_parashari_narrative_highlights_suppressed_caution(self) -> None:
        payload = compose_parashari_narrative(
            {
                "area": "career",
                "strength": "weak",
                "strength_score": 24.0,
                "resolution": {
                    "dominant_outcome": "suppressed",
                    "dominant_reasoning": "Primary conclusion: suppressed due to dasha inactivity.",
                    "suppressed_factors": [{"factor": "dasha_activation", "reason": "inactive"}],
                },
            }
        )

        self.assertIn("Caution:", payload["caution_text"])
        self.assertIn("suppressed", payload["caution_text"].lower())
        self.assertIn("dasha", payload["caution_text"].lower())

    def test_language_switch_keeps_order_without_raw_keys(self) -> None:
        context = {
            "area": "career",
            "yoga": "Raj Yoga",
            "strength": "strong",
            "strength_score": 79.1,
            "agreement_level": "high",
            "concordance_score": 0.84,
            "karaka_source": "supportive",
            "timing": {
                "mahadasha": "Jupiter",
                "antardasha": "Venus",
                "activation_level": "high",
            },
            "transit": {"support_state": "amplifying"},
            "resolution": {
                "dominant_outcome": "tempered",
                "dominant_factor": "dasha_activation",
                "suppressed_factors": [{"factor": "transit_trigger"}],
            },
        }

        for language in ("en", "hi", "or"):
            payload = compose_parashari_narrative({**context, "language": language})
            self.assertTrue(payload["promise_text"])
            self.assertTrue(payload["strength_text"])
            self.assertTrue(payload["timing_text"])
            self.assertTrue(payload["caution_text"])
            self.assertNotIn("prediction.parashari", payload["final_narrative"])

            ordered = [
                payload["promise_text"],
                payload["strength_text"],
                payload["timing_text"],
                payload["caution_text"],
            ]
            positions = [payload["final_narrative"].find(item) for item in ordered]
            self.assertTrue(all(pos >= 0 for pos in positions))
            self.assertEqual(positions, sorted(positions))

    def test_missing_key_detection_fails_cleanly_without_key_leakage(self) -> None:
        with patch(
            "core.predictions.rule_service.validate_parashari_localization",
            return_value={
                "missing_in_language": ["prediction.parashari.strength.strong_indication"],
                "missing_in_default": [],
            },
        ):
            payload = compose_parashari_narrative({"language": "hi", "area": "career"})

        self.assertTrue(payload["final_narrative"])
        self.assertNotIn("prediction.parashari", payload["final_narrative"])
        self.assertIn(":", payload["promise_text"])
        self.assertIn(":", payload["strength_text"])
        self.assertIn(":", payload["timing_text"])
        self.assertIn(":", payload["caution_text"])

    def test_translation_placeholders_match_across_languages(self) -> None:
        translation_dir = Path(__file__).resolve().parents[1] / "app" / "data" / "translations"
        payloads = {
            language: json.loads((translation_dir / f"{language}.json").read_text(encoding="utf-8"))
            for language in ("en", "hi", "or")
        }
        formatter = string.Formatter()
        en_parashari = payloads["en"]["prediction"]["parashari"]

        for key_path in _flatten_leaf_key_paths(en_parashari, prefix="prediction.parashari"):
            en_value = _read_path(payloads["en"], key_path)
            if not isinstance(en_value, str):
                continue
            expected_fields = {name for _, name, _, _ in formatter.parse(en_value) if name}

            for language in ("hi", "or"):
                value = _read_path(payloads[language], key_path)
                self.assertIsInstance(value, str, msg=f"{language}:{key_path}")
                actual_fields = {name for _, name, _, _ in formatter.parse(value) if name}
                self.assertEqual(
                    expected_fields,
                    actual_fields,
                    msg=f"Placeholder mismatch for {language}:{key_path}",
                )

    def test_validate_parashari_localization_has_no_missing_for_supported_languages(self) -> None:
        for language in ("en", "hi", "or"):
            result = validate_parashari_localization(language)
            self.assertEqual([], result["missing_in_default"])
            self.assertEqual([], result["missing_in_language"])


def _flatten_leaf_key_paths(payload: dict, prefix: str) -> list[str]:
    keys: list[str] = []
    for key, value in payload.items():
        scoped = f"{prefix}.{key}"
        if isinstance(value, dict):
            keys.extend(_flatten_leaf_key_paths(value, scoped))
        else:
            keys.append(scoped)
    return keys


def _read_path(payload: dict, key_path: str):
    current = payload
    for part in key_path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


if __name__ == "__main__":
    unittest.main()
