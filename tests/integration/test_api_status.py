from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

try:
    from aiohttp import ClientSession, UnixConnector
    from avreamd.app import AvreamDaemon
    from avreamd.config import resolve_paths
    HAS_AIOHTTP = True
except ImportError:  # pragma: no cover - environment dependency
    ClientSession = None  # type: ignore[assignment]
    UnixConnector = None  # type: ignore[assignment]
    AvreamDaemon = None  # type: ignore[assignment]
    resolve_paths = None  # type: ignore[assignment]
    HAS_AIOHTTP = False


class ApiStatusTests(unittest.IsolatedAsyncioTestCase):
    async def test_status_endpoint_returns_success_envelope(self) -> None:
        if not HAS_AIOHTTP:
            self.skipTest("aiohttp not installed in this environment")

        assert resolve_paths is not None
        assert AvreamDaemon is not None
        assert ClientSession is not None
        assert UnixConnector is not None

        with tempfile.TemporaryDirectory() as tmp_dir:
            socket_path = Path(tmp_dir) / "daemon.sock"
            paths = resolve_paths(socket_override=str(socket_path))
            daemon = AvreamDaemon(paths)

            await daemon.start()
            try:
                connector = UnixConnector(path=str(paths.socket_path))
                async with ClientSession(connector=connector) as session:
                    async with session.get("http://localhost/status") as resp:
                        status = resp.status
                        body = await resp.json()
            finally:
                await daemon.stop()

        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertIn("runtime", body["data"])
        self.assertEqual(body["data"]["service"]["daemon"], "avreamd")
        self.assertIn("video_runtime", body["data"])


if __name__ == "__main__":
    unittest.main()
