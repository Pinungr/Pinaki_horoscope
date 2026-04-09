from __future__ import annotations

import unittest

from core.engines.functional_nature import FunctionalNatureEngine, get_functional_nature


class FunctionalNatureEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = FunctionalNatureEngine()

    def test_saturn_changes_role_across_lagnas(self) -> None:
        self.assertEqual("malefic", self.engine.get_functional_nature("aries", "saturn"))
        self.assertEqual("yogakaraka", self.engine.get_functional_nature("libra", "saturn"))

    def test_yogakaraka_identification_for_taurus_and_libra(self) -> None:
        taurus_roles = self.engine.get_planet_roles("taurus")
        libra_roles = self.engine.get_planet_roles("libra")

        self.assertEqual("yogakaraka", taurus_roles["saturn"])
        self.assertEqual("yogakaraka", libra_roles["saturn"])

    def test_dual_lordship_mixed_case_can_be_neutral(self) -> None:
        # Aries Lagna: Mars owns 1 and 8, so mixed ownership should not force benefic/malefic.
        self.assertEqual("neutral", self.engine.get_functional_nature("aries", "mars"))

    def test_profile_contains_structured_matrix(self) -> None:
        profile = self.engine.get_functional_profile("aries")

        self.assertEqual("aries", profile["lagna"])
        self.assertIn("house_lords", profile)
        self.assertIn("planet_houses", profile)
        self.assertIn("roles", profile)
        self.assertIn("saturn", profile["roles"])
        self.assertEqual("malefic", profile["roles"]["saturn"])

    def test_module_level_get_functional_nature_helper(self) -> None:
        self.assertEqual("yogakaraka", get_functional_nature("libra", "saturn"))


if __name__ == "__main__":
    unittest.main()
