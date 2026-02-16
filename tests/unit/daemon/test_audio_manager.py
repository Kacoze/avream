from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from typing import Any, cast

from avreamd.core.state_store import DaemonStateStore
from avreamd.managers.audio_manager import AudioManager


class _PipewireStub:
    def __init__(self, available: bool, running: bool) -> None:
        self._available = available
        self._running = running
        self.pw_loopback = None

    def available(self) -> bool:
        return self._available

    def running(self) -> bool:
        return self._running

    def supports_native_virtual_mic(self) -> bool:
        return False


class AudioManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_audio_start_pipewire(self) -> None:
        class _PactlStub:
            available = True

            def list_modules(self) -> list[dict[str, str]]:
                return []

            def default_source(self) -> str:
                return "alsa_input.usb-test-mic"

            def list_sources(self) -> list[str]:
                return ["alsa_input.usb-test-mic"]

            def load_module(self, _name: str, _args: list[str]) -> int:
                return 1

            def list_sink_inputs_detailed(self) -> list[dict[str, object]]:
                return [{"id": "12", "properties": {"application.name": "scrcpy"}}]

            def move_sink_input(self, _sink_input_id: int, _sink_name: str) -> None:
                return

            def unload_module(self, _module_id: int) -> None:
                return

        class _PrivStub:
            async def call(self, _action: str, _params: dict) -> dict:
                return {}

        with tempfile.TemporaryDirectory() as tmp:
            manager = AudioManager(
                state_store=DaemonStateStore(),
                pipewire=cast(Any, _PipewireStub(True, True)),
                pactl=cast(Any, _PactlStub()),
                privilege_client=cast(Any, _PrivStub()),
                state_dir=Path(tmp),
            )
            result = await manager.start("pipewire")
            self.assertEqual(result["backend"], "pipewire")

    async def test_audio_start_fallback(self) -> None:
        class _PactlStub:
            available = False

            def list_sink_inputs_detailed(self) -> list[dict[str, object]]:
                return []

            def move_sink_input(self, _sink_input_id: int, _sink_name: str) -> None:
                return

        class _PrivStub:
            async def call(self, _action: str, _params: dict) -> dict:
                return {}

        with tempfile.TemporaryDirectory() as tmp:
            manager = AudioManager(
                state_store=DaemonStateStore(),
                pipewire=cast(Any, _PipewireStub(False, False)),
                pactl=cast(Any, _PactlStub()),
                privilege_client=cast(Any, _PrivStub()),
                state_dir=Path(tmp),
            )
            result = await manager.start("pipewire")
            self.assertEqual(result["backend"], "snd_aloop")


if __name__ == "__main__":
    unittest.main()
