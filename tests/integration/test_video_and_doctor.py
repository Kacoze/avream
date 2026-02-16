from __future__ import annotations

import os
import stat
import tempfile
import textwrap
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


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


class VideoPhoneIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_phone_video_start_stop_and_audio_start_stop(self) -> None:
        if not HAS_AIOHTTP:
            self.skipTest("aiohttp not installed in this environment")
        assert resolve_paths is not None
        assert AvreamDaemon is not None
        assert ClientSession is not None
        assert UnixConnector is not None

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            mock_bin = tmp / "bin"
            mock_bin.mkdir(parents=True)

            _write_executable(
                mock_bin / "adb",
                textwrap.dedent(
                    """#!/usr/bin/env bash
                    if [ "$1" = "devices" ]; then
                      echo "List of devices attached"
                      echo "ABC123\tdevice"
                      echo "192.168.1.20:5555\tdevice"
                      exit 0
                    fi
                    if [ "$1" = "version" ]; then
                      echo "Android Debug Bridge version 1.0.41"
                      exit 0
                    fi
                    if [ "$1" = "-s" ] && [ "$3" = "tcpip" ]; then
                      echo "restarting in TCP mode port: 5555"
                      exit 0
                    fi
                    if [ "$1" = "-s" ] && [ "$3" = "shell" ] && [ "$4" = "ip" ]; then
                      if [ "$9" = "wlan0" ]; then
                        echo "4: wlan0    inet 192.168.1.20/24 brd 192.168.1.255 scope global wlan0"
                      else
                        echo "4: wlan0    inet 192.168.1.20/24 brd 192.168.1.255 scope global wlan0"
                      fi
                      exit 0
                    fi
                    if [ "$1" = "-s" ] && [ "$3" = "shell" ] && [ "$4" = "getprop" ] && [ "$5" = "ro.serialno" ]; then
                      echo "PHONE123"
                      exit 0
                    fi
                    if [ "$1" = "-s" ] && [ "$3" = "shell" ] && [ "$4" = "getprop" ] && [ "$5" = "ro.boot.serialno" ]; then
                      echo "PHONE123"
                      exit 0
                    fi
                    if [ "$1" = "connect" ] || [ "$1" = "disconnect" ]; then
                      echo "ok"
                      exit 0
                    fi
                    exit 0
                    """
                ),
            )

            _write_executable(
                mock_bin / "scrcpy",
                textwrap.dedent(
                    """#!/usr/bin/env bash
                    if [ "$1" = "--version" ]; then
                      echo "scrcpy 0.0.0"
                      exit 0
                    fi
                    trap 'exit 0' TERM INT
                    while true; do sleep 1; done
                    """
                ),
            )

            _write_executable(
                mock_bin / "pactl",
                textwrap.dedent(
                    """#!/usr/bin/env bash
                    if [ "$1" = "load-module" ]; then
                      echo "42"
                      exit 0
                    fi
                    if [ "$1" = "unload-module" ]; then
                      exit 0
                    fi
                    if [ "$1" = "info" ]; then
                      echo "Server String: mock"
                      exit 0
                    fi
                    exit 0
                    """
                ),
            )

            helper = tmp / "helper.sh"
            _write_executable(
                helper,
                textwrap.dedent(
                    """#!/usr/bin/env bash
                    cat >/dev/null
                    printf '%s\n' '{"ok": true, "data": {"action": "mock"}}'
                    """
                ),
            )

            old_path = os.environ.get("PATH", "")
            os.environ["PATH"] = f"{mock_bin}:{old_path}"
            os.environ["AVREAM_HELPER_MODE"] = "direct"
            os.environ["AVREAM_HELPER_BIN"] = str(helper)

            socket_path = tmp / "daemon.sock"
            paths = resolve_paths(socket_override=str(socket_path))
            daemon = AvreamDaemon(paths)

            await daemon.start()
            try:
                connector = UnixConnector(path=str(paths.socket_path))
                async with ClientSession(connector=connector) as session:
                    async with session.get("http://localhost/android/devices") as resp:
                        self.assertEqual(resp.status, 200)
                        devices = await resp.json()
                        self.assertTrue(devices["ok"])
                        self.assertEqual(len(devices["data"]["devices"]), 1)
                        self.assertEqual(set(devices["data"]["devices"][0]["transports"]), {"usb", "wifi"})
                        self.assertIn("wifi_candidate_endpoint", devices["data"]["devices"][0])

                    async with session.post("http://localhost/android/wifi/setup", json={"serial": "ABC123"}) as resp:
                        self.assertEqual(resp.status, 200)
                        wifi_setup = await resp.json()
                        self.assertTrue(wifi_setup["ok"])
                        self.assertEqual(wifi_setup["data"]["endpoint"], "192.168.1.20:5555")

                    async with session.post("http://localhost/android/wifi/connect", json={"endpoint": "192.168.1.20"}) as resp:
                        self.assertEqual(resp.status, 200)
                        wifi_connect = await resp.json()
                        self.assertTrue(wifi_connect["ok"])
                        self.assertEqual(wifi_connect["data"]["endpoint"], "192.168.1.20:5555")

                    async with session.post(
                        "http://localhost/video/start",
                        json={"serial": "ABC123", "camera_facing": "back", "preview_window": True},
                    ) as resp:
                        self.assertEqual(resp.status, 200)
                        started = await resp.json()
                        self.assertTrue(started["ok"])
                        self.assertEqual(started["data"]["source"]["type"], "android")
                        self.assertEqual(started["data"]["source"]["camera_facing"], "back")
                        self.assertTrue(started["data"]["source"]["preview_window"])
                        self.assertEqual(started["data"]["audio"]["state"], "RUNNING")

                    async with session.post("http://localhost/video/stop", json={}) as resp:
                        self.assertEqual(resp.status, 200)
                        stopped = await resp.json()
                        self.assertTrue(stopped["ok"])
                        self.assertEqual(stopped["data"]["audio"]["state"], "STOPPED")

                    async with session.post("http://localhost/android/wifi/disconnect", json={"endpoint": "192.168.1.20"}) as resp:
                        self.assertEqual(resp.status, 200)
                        wifi_disconnect = await resp.json()
                        self.assertTrue(wifi_disconnect["ok"])
                        self.assertEqual(wifi_disconnect["data"]["endpoint"], "192.168.1.20:5555")
            finally:
                await daemon.stop()
                os.environ["PATH"] = old_path
                os.environ.pop("AVREAM_HELPER_MODE", None)
                os.environ.pop("AVREAM_HELPER_BIN", None)


if __name__ == "__main__":
    unittest.main()
