from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.services.language_manager import LanguageManager


class LanguageManagerFallbackTests(unittest.TestCase):
    def test_missing_translation_key_falls_back_to_english_safely(self) -> None:
        # Create a workspace-local temp directory to avoid system temp permission issues
        temp_root = Path("tmp")
        temp_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_root) as temp_dir:
            translations_dir = Path(temp_dir)
            (translations_dir / "en.json").write_text(
                json.dumps(
                    {
                        "meta": {"code": "en", "native_name": "English"},
                        "report": {"title": "Offline Horoscope Report"},
                    }
                ),
                encoding="utf-8",
            )
            (translations_dir / "hi.json").write_text(
                json.dumps({"meta": {"code": "hi", "native_name": "Hindi"}, "report": {}}),
                encoding="utf-8",
            )

            manager = LanguageManager("hi", translations_dir=translations_dir)
            self.assertEqual("Offline Horoscope Report", manager.get_text("report.title"))
            self.assertEqual("report.unknown_key", manager.get_text("report.unknown_key"))


if __name__ == "__main__":
    unittest.main()
