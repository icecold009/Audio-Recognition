from __future__ import annotations

import unittest

from scripts.benchmark import _aggregate, _matches, _normalise


class BenchmarkTests(unittest.TestCase):
    def test_normalisation_handles_case_accents_and_punctuation(self):
        self.assertEqual(_normalise("Beyoncé — Déjà Vu!"), "beyonce deja vu")

    def test_matches_accepts_documented_aliases(self):
        self.assertTrue(_matches("The Weeknd", "The Weeknd|Weeknd"))
        self.assertFalse(_matches("Another Artist", "The Weeknd|Weeknd"))

    def test_aggregate_reports_accuracy_by_clip_length_and_failures(self):
        records = [
            {
                "backend": "rapidapi",
                "clip_id": "track-001_4s",
                "clip_length_s": 4.0,
                "status": "matched",
                "correct": True,
                "latency_ms": 100.0,
            },
            {
                "backend": "rapidapi",
                "clip_id": "track-001_8s",
                "clip_length_s": 8.0,
                "status": "no_match",
                "correct": False,
                "failure_reason": "provider returned no match",
                "latency_ms": 200.0,
            },
            {
                "backend": "rapidapi",
                "clip_id": "track-001_15s",
                "clip_length_s": 15.0,
                "status": "not_configured",
                "correct": False,
            },
        ]

        summary = _aggregate(records, "rapidapi")

        self.assertEqual(summary["correct"], 1)
        self.assertEqual(summary["attempted"], 2)
        self.assertEqual(summary["accuracy"], 0.5)
        self.assertEqual(summary["by_clip_length"]["4.0"]["accuracy"], 1.0)
        self.assertEqual(summary["by_clip_length"]["8.0"]["accuracy"], 0.0)
        self.assertIsNone(summary["by_clip_length"]["15.0"]["accuracy"])
        self.assertEqual(summary["failures"][0]["reason"], "provider returned no match")


if __name__ == "__main__":
    unittest.main()
