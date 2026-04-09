import unittest
from app.engine.prediction_scorer import (
    _choose_representative_sentence,
    _collapse_similar_sentences,
    _sentences_are_similar,
)

class ScorerDedupTests(unittest.TestCase):
    def test_yoga_sentences_are_never_similar_if_names_differ(self):
        s1 = "Hamsa Yoga: Jupiter is powerful in a kendra."
        s2 = "Gajakesari Yoga is present: Moon and Jupiter combine."
        
        # Should be False despite sharing tokens like "Yoga", "Jupiter", "kendra"
        self.assertFalse(_sentences_are_similar(s1, s2))

    def test_yoga_vs_generic_is_never_similar(self):
        s1 = "Gajakesari Yoga is present and provides wisdom."
        s2 = "Overall indications look strongly supportive."
        
        self.assertFalse(_sentences_are_similar(s1, s2))

    def test_slightly_different_yoga_phrasing_is_similar(self):
        s1 = "Gajakesari Yoga: Moon and Jupiter combine."
        s2 = "Gajakesari Yoga is present: Moon and Jupiter combine in a kendra."
        
        # These should be collapsed as they represent the SAME yoga
        self.assertTrue(_sentences_are_similar(s1, s2))

    def test_collapse_preserves_multiple_yogas(self):
        sentences = [
            "Hamsa Yoga: Jupiter is powerful.",
            "Gajakesari Yoga: Moon and Jupiter combine.",
            "Hamsa Yoga is present.", # Should collapse into the first one
            "Overall results are good."
        ]
        collapsed = _collapse_similar_sentences(sentences)
        
        # Should have 3 unique clusters: Hamsa, Gajakesari, Overall
        self.assertEqual(len(collapsed), 3)
        text = " ".join(collapsed).lower()
        self.assertIn("hamsa", text)
        self.assertIn("gajakesari", text)
        self.assertIn("overall", text)

    def test_result_key_style_yoga_identifier_is_not_similar_to_generic_sentence(self):
        s1 = "gajakesari_yoga is present and supports wisdom."
        s2 = "This combination is present and supports wisdom."

        self.assertFalse(_sentences_are_similar(s1, s2))

    def test_representative_sentence_prefers_identifier_bearing_text(self):
        sentences = [
            "This combination supports wisdom, recognition, and emotional strength.",
            "Gajakesari Yoga is present.",
        ]

        representative = _choose_representative_sentence(sentences)
        self.assertIn("gajakesari", representative.lower())

    def test_generic_near_identical_sentences_still_collapse(self):
        sentences = [
            "Overall results are stable and supportive.",
            "Overall results remain stable and supportive.",
        ]

        collapsed = _collapse_similar_sentences(sentences)
        self.assertEqual(1, len(collapsed))

if __name__ == "__main__":
    unittest.main()
