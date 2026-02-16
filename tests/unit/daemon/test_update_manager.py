from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from avreamd.config import AvreamPaths
from avreamd.core.state_store import DaemonStateStore
from avreamd.managers.update_manager import UpdateManager


class _VideoStub:
    async def stop(self) -> dict[str, object]:
        return {"state": "STOPPED"}


class _AudioStub:
    async def stop(self) -> dict[str, object]:
        return {"state": "STOPPED"}


class UpdateManagerTests(unittest.IsolatedAsyncioTestCase):
    def _paths(self, root: Path) -> AvreamPaths:
        runtime = root / "runtime"
        config = root / "config"
        state = root / "state"
        log = state / "logs"
        cache = root / "cache"
        for p in (runtime, config, state, log, cache):
            p.mkdir(parents=True, exist_ok=True)
        return AvreamPaths(
            runtime_dir=runtime,
            socket_path=runtime / "daemon.sock",
            config_dir=config,
            state_dir=state,
            log_dir=log,
            cache_dir=cache,
        )

    async def test_version_compare(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mgr = UpdateManager(
                paths=self._paths(Path(td)),
                state_store=DaemonStateStore(),
                video_manager=_VideoStub(),
                audio_manager=_AudioStub(),
            )
            self.assertTrue(mgr._is_newer_version("1.0.1", "1.0.0"))
            self.assertFalse(mgr._is_newer_version("1.0.0", "1.0.0"))
            self.assertFalse(mgr._is_newer_version("1.0.0-beta.1", "1.0.0"))

    async def test_config_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mgr = UpdateManager(
                paths=self._paths(Path(td)),
                state_store=DaemonStateStore(),
                video_manager=_VideoStub(),
                audio_manager=_AudioStub(),
            )
            cfg = await mgr.set_config(auto_check="weekly", channel="stable")
            self.assertEqual(cfg["auto_check"], "weekly")
            loaded = await mgr.get_config()
            self.assertEqual(loaded["auto_check"], "weekly")


if __name__ == "__main__":
    unittest.main()
