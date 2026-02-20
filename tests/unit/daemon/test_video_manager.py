from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any, cast

from avreamd.core.state_store import DaemonStateStore
from avreamd.managers.video_manager import VideoManager


class _Process:
    def __init__(self) -> None:
        self.returncode: int | None = None


class _Managed:
    def __init__(self) -> None:
        self.process = _Process()


class _SupervisorStub:
    def __init__(self) -> None:
        self._running = False
        self._last_exit = None

    async def start(self, _name: str, _command: list[str]) -> _Managed:
        self._running = True
        return _Managed()

    async def stop(self, _name: str) -> None:
        self._running = False

    async def wait(self, _name: str) -> int | None:
        self._running = False
        self._last_exit = 1
        return 1

    def running(self, _name: str) -> bool:
        return self._running

    def last_exit_code(self, _name: str) -> int | None:
        return self._last_exit

    def latest_log_path(self, _name: str) -> str:
        return "/tmp/video-android.log"


class _BackendStub:
    class _Source:
        def __init__(self, serial: str) -> None:
            self.serial = serial

    async def list_sources(self) -> list[dict[str, str]]:
        return [{"type": "android", "serial": "ABC123", "state": "device"}]

    async def select_default_source(self, preferred_serial: str | None = None):
        return _BackendStub._Source(preferred_serial or "ABC123")

    def build_start_command(self, **_kwargs) -> list[str]:
        return ["/usr/bin/scrcpy", "--no-window"]


class _PrivilegeStub:
    async def call(self, action: str, _payload: dict[str, object]) -> dict[str, object]:
        if action == "v4l2.status":
            return {"requires_reload": False}
        return {}


class _V4L2Stub:
    video_nr = 10
    device_path = Path("/dev/video10")

    def device_blockers(self) -> list[int]:
        return []


class _AudioStub:
    async def start(self, backend: str = "pipewire") -> dict[str, object]:
        return {"state": "RUNNING", "backend": backend}

    async def stop(self) -> dict[str, object]:
        return {"state": "STOPPED"}


class VideoManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_and_stop(self) -> None:
        manager = VideoManager(
            state_store=DaemonStateStore(),
            backend=cast(Any, _BackendStub()),
            supervisor=cast(Any, _SupervisorStub()),
            privilege_client=cast(Any, _PrivilegeStub()),
            v4l2=cast(Any, _V4L2Stub()),
            audio_manager=cast(Any, _AudioStub()),
        )

        started = await manager.start(serial="ABC123", camera_facing="front", camera_rotation=0, preview_window=False)
        self.assertEqual(started["state"], "RUNNING")
        self.assertEqual(started["source"]["serial"], "ABC123")

        stopped = await manager.stop()
        self.assertEqual(stopped["state"], "STOPPED")
        self.assertIn("post_stop_reset", stopped)

    async def test_runtime_status_contains_reconnect(self) -> None:
        manager = VideoManager(
            state_store=DaemonStateStore(),
            backend=cast(Any, _BackendStub()),
            supervisor=cast(Any, _SupervisorStub()),
            privilege_client=cast(Any, _PrivilegeStub()),
            v4l2=cast(Any, _V4L2Stub()),
            audio_manager=cast(Any, _AudioStub()),
        )
        status = await manager.runtime_status()
        self.assertIn("reconnect", status)
        self.assertIn("log_pointers", status)


if __name__ == "__main__":
    unittest.main()
