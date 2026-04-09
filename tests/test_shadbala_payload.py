from __future__ import annotations

import unittest

from app.engine.shadbala_engine_wrapper import calculate_shadbala, normalize_shadbala_payload
from app.models.domain import ChartData


_REQUIRED_FIELDS = {
    "planet",
    "sthana_bala",
    "dik_bala",
    "kala_bala",
    "chestha_bala",
    "naisargika_bala",
    "drik_bala",
    "is_vargottama",
    "total",
}


class ShadbalaPayloadTests(unittest.TestCase):
    def _assert_planet_schema(self, payload: dict, planet: str) -> None:
        self.assertIn(planet, payload)
        entry = payload[planet]
        self.assertEqual(_REQUIRED_FIELDS, set(entry.keys()))
        self.assertEqual(planet, entry["planet"])
        self.assertIsInstance(entry["is_vargottama"], bool)
        for field in _REQUIRED_FIELDS - {"planet", "is_vargottama"}:
            self.assertIsInstance(entry[field], float)

        expected_total = round(
            entry["sthana_bala"]
            + entry["dik_bala"]
            + entry["kala_bala"]
            + entry["chestha_bala"]
            + entry["naisargika_bala"]
            + entry["drik_bala"],
            2,
        )
        self.assertEqual(expected_total, entry["total"])

    def test_calculate_shadbala_returns_normalized_schema_for_available_planets(self) -> None:
        rows = [
            ChartData(user_id=1, planet_name="Sun", sign="Aries", house=1, degree=10.0, absolute_longitude=10.0),
            ChartData(user_id=1, planet_name="Moon", sign="Taurus", house=2, degree=3.0, absolute_longitude=33.0),
            ChartData(user_id=1, planet_name="Ascendant", sign="Aries", house=1, degree=0.0, absolute_longitude=0.0),
        ]

        payload = calculate_shadbala(rows)

        self._assert_planet_schema(payload, "sun")
        self._assert_planet_schema(payload, "moon")

    def test_calculate_shadbala_returns_default_schema_when_requirements_missing(self) -> None:
        # Missing ascendant prevents full Shadbala calculation, but payload shape should remain stable.
        rows = [
            ChartData(user_id=1, planet_name="Sun", sign="Aries", house=1, degree=10.0, absolute_longitude=10.0),
        ]

        payload = calculate_shadbala(rows)

        self._assert_planet_schema(payload, "sun")
        self.assertEqual(0.0, payload["sun"]["total"])

    def test_normalize_shadbala_payload_sanitizes_malformed_rows(self) -> None:
        raw_payload = {
            "sun": {
                "planet": "Sun",
                "sthana_bala": "bad-value",
                "dik_bala": 12.5,
                "kala_bala": None,
                "chestha_bala": "7.25",
                "naisargika_bala": 60,
                "drik_bala": "3",
                "is_vargottama": "yes",
            }
        }

        normalized = normalize_shadbala_payload(raw_payload)

        self._assert_planet_schema(normalized, "sun")
        self.assertEqual(0.0, normalized["sun"]["sthana_bala"])
        self.assertEqual(12.5, normalized["sun"]["dik_bala"])
        self.assertEqual(7.25, normalized["sun"]["chestha_bala"])
        self.assertTrue(normalized["sun"]["is_vargottama"])


if __name__ == "__main__":
    unittest.main()
