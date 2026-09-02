from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from content_planner.clip_ai import analyze_cuts
from content_planner.ui import ContentPlannerApp
from content_planner.video_subtitles import Subtitle, write_captions


class RegressionTests(unittest.TestCase):
    def test_ai_cuts_are_clamped_filtered_deduplicated_and_limited(self) -> None:
        payload = {
            "cuts": [
                {"start": -5, "end": 30, "title": "válido", "summary": "a", "score": 120},
                {"start": 10, "end": 35, "title": "sobreposto", "summary": "b", "score": 50},
                {"start": 40, "end": 45, "title": "curto", "summary": "c", "score": 50},
                {"start": 50, "end": 80, "title": "segundo", "summary": "d", "score": -1},
                {"start": 90, "end": 200, "title": "fora", "summary": "e", "score": 50},
            ]
        }
        response = Mock(ok=True)
        response.json.return_value = {"output_text": json.dumps(payload)}
        with patch("content_planner.clip_ai.requests.post", return_value=response):
            result = analyze_cuts([Subtitle(0, 100, "fala")], "chave", limit=2)
        self.assertEqual([(item.start, item.end) for item in result], [(0, 30), (50, 80)])
        self.assertEqual([item.score for item in result], [100, 0])

    def test_ai_zero_limit_does_not_make_a_request(self) -> None:
        with patch("content_planner.clip_ai.requests.post") as request:
            self.assertEqual(analyze_cuts([Subtitle(0, 100, "fala")], "chave", limit=0), [])
        request.assert_not_called()

    def test_caption_export_creates_parent_folder(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "nova" / "legendas.srt"
            write_captions([Subtitle(0, 1, "Olá")], output)
            self.assertTrue(output.is_file())
            self.assertIn("Olá", output.read_text(encoding="utf-8"))

    def test_year_validation_rejects_calendar_out_of_range(self) -> None:
        self.assertEqual(ContentPlannerApp._parse_year(None, "2026"), 2026)
        self.assertIsNone(ContentPlannerApp._parse_year(None, "0"))
        self.assertIsNone(ContentPlannerApp._parse_year(None, "10000"))
        self.assertIsNone(ContentPlannerApp._parse_year(None, "abc"))


if __name__ == "__main__":
    unittest.main()
