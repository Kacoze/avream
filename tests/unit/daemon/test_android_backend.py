from __future__ import annotations

import unittest
from typing import Any, cast

from avreamd.backends.android_video import AndroidVideoBackend


class _AdbStub:
    def __init__(self, devices):
        self._devices = devices
        self.adb_bin = "/usr/bin/adb"

    @property
    def available(self):
        return True

    async def list_devices(self):
        return list(self._devices)

    @staticmethod
    def transport_of(serial: str) -> str:
        return "wifi" if ":" in serial else "usb"


class _ScrcpyStub:
    @property
    def available(self):
        return True

    def command_for_android_camera(
        self,
        *,
        serial: str,
        sink_path: str,
        preset: str,
        camera_facing: str | None = None,
        camera_rotation: int | None = None,
        preview_window: bool = False,
        enable_audio: bool = False,
        extra_args=None,
    ):
        cmd = ["scrcpy", "-s", serial, f"--v4l2-sink={sink_path}", f"--preset={preset}"]
        if camera_facing:
            cmd.append(f"--camera-facing={camera_facing}")
        if camera_rotation in {0, 90, 180, 270}:
            cmd.append(f"--capture-orientation={camera_rotation}")
        if preview_window:
            cmd.append("--window-title=AVream Preview")
        else:
            cmd.append("--no-window")
        if enable_audio:
            cmd.append("--audio-source=mic")
        else:
            cmd.append("--no-audio")
        return cmd


class AndroidBackendTests(unittest.IsolatedAsyncioTestCase):
    async def test_prefer_transport_usb(self):
        backend = AndroidVideoBackend(
            adb=cast(Any, _AdbStub(
                [
                    {"serial": "192.168.1.2:5555", "state": "device"},
                    {"serial": "ABC123", "state": "device"},
                ]
            )),
            scrcpy=cast(Any, _ScrcpyStub()),
        )
        src = await backend.select_default_source(preferred_transport="usb")
        self.assertEqual(src.serial, "ABC123")

    async def test_preferred_serial_must_be_ready(self):
        backend = AndroidVideoBackend(
            adb=cast(Any, _AdbStub(
                [
                    {"serial": "ABC123", "state": "unauthorized"},
                    {"serial": "XYZ999", "state": "device"},
                ]
            )),
            scrcpy=cast(Any, _ScrcpyStub()),
        )
        with self.assertRaises(Exception):
            await backend.select_default_source(preferred_serial="ABC123")

    async def test_build_start_command_enables_audio_when_requested(self):
        backend = AndroidVideoBackend(
            adb=cast(Any, _AdbStub([{"serial": "ABC123", "state": "device"}])),
            scrcpy=cast(Any, _ScrcpyStub()),
        )
        cmd = backend.build_start_command(serial="ABC123", sink_path="/dev/video10", enable_audio=True)
        self.assertNotIn("--no-audio", cmd)
        self.assertIn("--audio-source=mic", cmd)

    async def test_build_start_command_includes_camera_facing(self):
        backend = AndroidVideoBackend(
            adb=cast(Any, _AdbStub([{"serial": "ABC123", "state": "device"}])),
            scrcpy=cast(Any, _ScrcpyStub()),
        )
        cmd = backend.build_start_command(serial="ABC123", sink_path="/dev/video10", camera_facing="back")
        self.assertIn("--camera-facing=back", cmd)

    async def test_build_start_command_respects_preview_window_flag(self):
        backend = AndroidVideoBackend(
            adb=cast(Any, _AdbStub([{"serial": "ABC123", "state": "device"}])),
            scrcpy=cast(Any, _ScrcpyStub()),
        )
        cmd = backend.build_start_command(serial="ABC123", sink_path="/dev/video10", preview_window=True)
        self.assertIn("--window-title=AVream Preview", cmd)
        self.assertNotIn("--no-window", cmd)


if __name__ == "__main__":
    unittest.main()
