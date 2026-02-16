from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

try:
    from aiohttp import ClientSession, UnixConnector
    from avreamd.app import AvreamDaemon
    from avreamd.config import resolve_paths

    HAS_AIOHTTP = True
except ImportError:  # pragma: no cover
    ClientSession = None  # type: ignore[assignment]
    UnixConnector = None  # type: ignore[assignment]
    AvreamDaemon = None  # type: ignore[assignment]
    resolve_paths = None  # type: ignore[assignment]
    HAS_AIOHTTP = False


class ApiContractTests(unittest.IsolatedAsyncioTestCase):
    async def _request(self, method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
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
                    async with session.request(method, f"http://localhost{path}", json=payload) as resp:
                        return resp.status, await resp.json()
            finally:
                await daemon.stop()

    def _assert_success_envelope(self, body: dict) -> None:
        self.assertTrue(body["ok"])
        self.assertIsNone(body["error"])
        self.assertIn("data", body)
        self.assertIn("request_id", body)
        self.assertIn("ts", body)

    def _assert_error_envelope(self, body: dict, *, code: str) -> None:
        self.assertFalse(body["ok"])
        self.assertIsNone(body["data"])
        self.assertEqual(body["error"]["code"], code)

    async def test_status_envelope_contract(self) -> None:
        if not HAS_AIOHTTP:
            self.skipTest("aiohttp not installed in this environment")
        status, body = await self._request("GET", "/status")
        self.assertEqual(status, 200)
        self._assert_success_envelope(body)

    async def test_audio_start_backend_validation(self) -> None:
        if not HAS_AIOHTTP:
            self.skipTest("aiohttp not installed in this environment")
        status, body = await self._request("POST", "/audio/start", {"backend": "invalid"})
        self.assertEqual(status, 400)
        self._assert_error_envelope(body, code="E_VALIDATION")

    async def test_video_reset_force_type_validation(self) -> None:
        if not HAS_AIOHTTP:
            self.skipTest("aiohttp not installed in this environment")
        status, body = await self._request("POST", "/video/reset", {"force": "nope"})
        self.assertEqual(status, 400)
        self._assert_error_envelope(body, code="E_VALIDATION")

    async def test_video_start_camera_facing_validation(self) -> None:
        if not HAS_AIOHTTP:
            self.skipTest("aiohttp not installed in this environment")
        status, body = await self._request("POST", "/video/start", {"camera_facing": "left"})
        self.assertEqual(status, 400)
        self._assert_error_envelope(body, code="E_VALIDATION")

    async def test_video_start_preview_window_validation(self) -> None:
        if not HAS_AIOHTTP:
            self.skipTest("aiohttp not installed in this environment")
        status, body = await self._request("POST", "/video/start", {"preview_window": "yes"})
        self.assertEqual(status, 400)
        self._assert_error_envelope(body, code="E_VALIDATION")

    async def test_android_devices_envelope(self) -> None:
        if not HAS_AIOHTTP:
            self.skipTest("aiohttp not installed in this environment")
        status, body = await self._request("GET", "/android/devices")
        if status == 412:
            self._assert_error_envelope(body, code="E_DEP_MISSING")
            return

        self.assertEqual(status, 200)
        self._assert_success_envelope(body)
        self.assertIn("devices", body["data"])
        self.assertIn("recommended", body["data"])

    async def test_android_wifi_setup_port_validation(self) -> None:
        if not HAS_AIOHTTP:
            self.skipTest("aiohttp not installed in this environment")
        status, body = await self._request("POST", "/android/wifi/setup", {"port": 70000})
        self.assertEqual(status, 400)
        self._assert_error_envelope(body, code="E_VALIDATION")


if __name__ == "__main__":
    unittest.main()
