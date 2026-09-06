from __future__ import annotations

import json
import runpy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from content_planner.davinci_integration import install_integration, integration_status
from content_planner.davinci_caption_worker import remap_captions, run_request
from content_planner.davinci_dialog import _write_result
from content_planner.video_subtitles import Subtitle, Word


ROOT = Path(__file__).resolve().parent.parent
SCRIPT_FUNCTIONS = runpy.run_path(str(ROOT / "assets" / "davinci" / "rafaau_timeline.py"))


class DavinciIntegrationTests(unittest.TestCase):
    def test_installs_script_ffmpeg_and_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            app_root = root / "app"
            source_script = app_root / "assets" / "davinci" / "rafaau_timeline.py"
            source_script.parent.mkdir(parents=True)
            source_script.write_text("# painel", encoding="utf-8")
            source_ffmpeg = root / "source" / "ffmpeg.exe"
            source_ffmpeg.parent.mkdir()
            source_ffmpeg.write_bytes(b"ffmpeg")
            environ = {"APPDATA": str(root / "roaming"), "LOCALAPPDATA": str(root / "local")}

            with patch("content_planner.davinci_integration._app_root", return_value=app_root), patch(
                "content_planner.davinci_integration.binary", return_value=str(source_ffmpeg)
            ):
                status = install_integration(environ)

            self.assertTrue(status.installed)
            self.assertEqual(status.script_path.read_text(encoding="utf-8"), "# painel")
            self.assertEqual(status.ffmpeg_path.read_bytes(), b"ffmpeg")
            config = json.loads((status.ffmpeg_path.parent / "config.json").read_text(encoding="utf-8"))
            self.assertEqual(Path(config["ffmpeg_path"]), status.ffmpeg_path.resolve())
            self.assertIn("--davinci-transcribe", config["transcription_command"])
            self.assertIn("--davinci-dialog", config["dialog_command"])
            self.assertTrue(integration_status(environ).installed)

    def test_reports_not_installed_without_both_files(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            status = integration_status({"APPDATA": str(root / "roaming"), "LOCALAPPDATA": str(root / "local")})
            self.assertFalse(status.installed)

    def test_dialog_result_protocol(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            request = Path(folder) / "dialog-request.json"
            _write_result(request, True)
            result = json.loads(request.with_suffix(".result.json").read_text(encoding="utf-8"))
            self.assertEqual(result, {"ok": True, "approved": True})


class DavinciTimelineLogicTests(unittest.TestCase):
    def test_parses_complete_and_trailing_silences(self) -> None:
        parse = SCRIPT_FUNCTIONS["parse_silences"]
        output = "silence_start: 0.2\nsilence_end: 1.4 | silence_duration: 1.2\nsilence_start: 8.0"
        self.assertEqual(parse(output, 10.0), [(0.2, 1.4), (8.0, 10.0)])

    def test_keeps_margin_around_speech(self) -> None:
        intervals = SCRIPT_FUNCTIONS["speaking_intervals"](10.0, [(0.0, 2.0), (5.0, 7.0)], 0.25)
        self.assertEqual(intervals, [(0.0, 0.25), (1.75, 5.25), (6.75, 10.0)])

    def test_parses_fractional_frame_rate_label(self) -> None:
        self.assertEqual(SCRIPT_FUNCTIONS["parse_frame_rate"]("29.97 DF"), 29.97)

    def test_remaps_caption_words_after_removed_silence(self) -> None:
        subtitles = [
            Subtitle(0, 8, "Olá mundo depois corte", [
                Word("Olá", 0.5, 1.0),
                Word("mundo", 1.1, 1.6),
                Word("depois", 6.0, 6.5),
                Word("corte", 6.6, 7.0),
            ])
        ]
        captions = remap_captions(subtitles, [(0.0, 2.0), (5.0, 8.0)], 20)
        self.assertEqual([caption.text for caption in captions], ["Olá mundo", "depois corte"])
        self.assertAlmostEqual(captions[1].start, 3.0)

    def test_all_spoken_intervals_become_sequential_source_ranges(self) -> None:
        context = SimpleNamespace(source_start=0, source_end=1110, fps=30.0)
        ranges = SCRIPT_FUNCTIONS["clip_frame_ranges"](
            context,
            [(0.0, 2.7), (4.4, 8.4), (9.0, 12.0), (14.0, 20.0)],
        )
        self.assertEqual(ranges, [(0, 81), (132, 252), (270, 360), (420, 600)])
        self.assertTrue(all(end > start for start, end in ranges))

    def test_caption_worker_writes_srt_and_result_protocol(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "video.mp4"
            source.touch()
            output = root / "legendas.srt"
            request = root / "request.json"
            request.write_text(json.dumps({
                "input_path": str(source),
                "output_path": str(output),
                "source_start_seconds": 0,
                "duration_seconds": 5,
                "kept_intervals": [[0, 5]],
                "chars_per_caption": 42,
            }), encoding="utf-8")
            words = [Word("Teste", 0.5, 0.9), Word("local", 1.0, 1.4)]
            with patch(
                "content_planner.davinci_caption_worker.transcribe_interval",
                return_value=[Subtitle(0.5, 1.4, "Teste local", words)],
            ):
                self.assertEqual(run_request(request), 0)
            self.assertIn("Teste local", output.read_text(encoding="utf-8"))
            result = json.loads(request.with_suffix(".result.json").read_text(encoding="utf-8"))
            self.assertTrue(result["ok"])


if __name__ == "__main__":
    unittest.main()
