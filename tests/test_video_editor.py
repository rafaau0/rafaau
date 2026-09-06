from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from content_planner.video_editor import find_davinci, launch_davinci, validate_davinci_executable


class VideoEditorTests(unittest.TestCase):
    def test_accepts_configured_resolve_executable(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            executable = Path(folder) / "Resolve.exe"
            executable.touch()
            self.assertEqual(validate_davinci_executable(executable), executable.resolve())
            self.assertEqual(find_davinci(executable), executable.resolve())

    def test_rejects_another_executable(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            executable = Path(folder) / "outro.exe"
            executable.touch()
            with self.assertRaises(ValueError):
                validate_davinci_executable(executable)

    def test_launches_without_using_a_shell(self) -> None:
        executable = Path("C:/Program Files/Blackmagic Design/DaVinci Resolve/Resolve.exe")
        with patch("content_planner.video_editor.find_davinci", return_value=executable), patch(
            "content_planner.video_editor.subprocess.Popen"
        ) as popen:
            self.assertEqual(launch_davinci(), executable)
        popen.assert_called_once_with([str(executable)], cwd=str(executable.parent), close_fds=True)


if __name__ == "__main__":
    unittest.main()
