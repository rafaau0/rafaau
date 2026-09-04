from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from content_planner.ffmpeg_tools import binary


class FFmpegToolsTests(unittest.TestCase):
    def test_uses_binary_extracted_by_pyinstaller(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            executable = root / "assets" / "ffmpeg" / "ffmpeg.exe"
            executable.parent.mkdir(parents=True)
            executable.touch()
            with (
                patch("content_planner.ffmpeg_tools.sys.frozen", True, create=True),
                patch("content_planner.ffmpeg_tools.sys._MEIPASS", str(root), create=True),
                patch("content_planner.ffmpeg_tools.sys.platform", "win32"),
                patch("content_planner.ffmpeg_tools.shutil.which", return_value=None),
            ):
                self.assertEqual(binary("ffmpeg"), str(executable))

    def test_bundled_binary_has_priority_over_path(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            executable = root / "assets" / "ffmpeg" / "ffprobe.exe"
            executable.parent.mkdir(parents=True)
            executable.touch()
            with (
                patch("content_planner.ffmpeg_tools.app_root", return_value=root),
                patch("content_planner.ffmpeg_tools.sys.platform", "win32"),
                patch("content_planner.ffmpeg_tools.shutil.which", return_value="C:\\outro\\ffprobe.exe"),
            ):
                self.assertEqual(binary("ffprobe"), str(executable))


if __name__ == "__main__":
    unittest.main()
