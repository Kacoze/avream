from __future__ import annotations

import unittest

from avreamd.integrations.scrcpy import ScrcpyAdapter


class ScrcpyAdapterTests(unittest.TestCase):
    def test_command_uses_no_window_by_default(self) -> None:
        adapter = ScrcpyAdapter(scrcpy_bin="/usr/bin/scrcpy")
        cmd = adapter.command_for_android_camera(
            serial="ABC123",
            sink_path="/dev/video10",
            preset="balanced",
            camera_facing="front",
            enable_audio=False,
        )
        self.assertIn("--no-window", cmd)
        self.assertIn("--camera-facing=front", cmd)
        self.assertIn("--video-source=camera", cmd)

    def test_command_enables_preview_window_when_requested(self) -> None:
        adapter = ScrcpyAdapter(scrcpy_bin="/usr/bin/scrcpy")
        cmd = adapter.command_for_android_camera(
            serial="ABC123",
            sink_path="/dev/video10",
            preset="balanced",
            preview_window=True,
            enable_audio=False,
        )
        self.assertIn("--window-title=AVream Preview", cmd)
        self.assertIn("--window-width=640", cmd)
        self.assertIn("--window-height=360", cmd)
        self.assertNotIn("--no-window", cmd)

    def test_command_enables_phone_mic_when_audio_requested(self) -> None:
        adapter = ScrcpyAdapter(scrcpy_bin="/usr/bin/scrcpy")
        cmd = adapter.command_for_android_camera(
            serial="ABC123",
            sink_path="/dev/video10",
            preset="balanced",
            enable_audio=True,
        )
        self.assertIn("--audio-source=mic", cmd)
        self.assertNotIn("--no-audio", cmd)

    def test_command_applies_capture_rotation_when_requested(self) -> None:
        adapter = ScrcpyAdapter(scrcpy_bin="/usr/bin/scrcpy")
        cmd = adapter.command_for_android_camera(
            serial="ABC123",
            sink_path="/dev/video10",
            preset="balanced",
            camera_rotation=270,
            enable_audio=False,
        )
        self.assertIn("--capture-orientation=270", cmd)


if __name__ == "__main__":
    unittest.main()
