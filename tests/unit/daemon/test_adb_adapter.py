from __future__ import annotations

import unittest

from avreamd.integrations.adb import AdbAdapter


class _StubAdbAdapter(AdbAdapter):
    def __init__(self) -> None:
        super().__init__(adb_bin="/usr/bin/adb")
        self.calls: list[list[str]] = []
        self.devices: list[dict[str, str]] = []

    async def list_devices(self) -> list[dict[str, str]]:
        return list(self.devices)

    async def _run(self, args: list[str]) -> dict[str, object]:
        self.calls.append(list(args))
        if args[:3] == ["-s", "USB123", "tcpip"]:
            return {"returncode": 0, "stdout": "restarting in TCP mode port: 5555", "stderr": "", "args": [self.adb_bin, *args]}
        if args[:8] == ["-s", "USB123", "shell", "ip", "-4", "-o", "addr", "show"] and args[-1] == "wlan0":
            return {
                "returncode": 0,
                "stdout": "4: wlan0    inet 192.168.1.20/24 brd 192.168.1.255 scope global wlan0\n",
                "stderr": "",
                "args": [self.adb_bin, *args],
            }
        if args[:8] == ["-s", "USB123", "shell", "ip", "-4", "-o", "addr", "show"]:
            return {
                "returncode": 0,
                "stdout": "4: wlan0    inet 192.168.1.20/24 brd 192.168.1.255 scope global wlan0\n",
                "stderr": "",
                "args": [self.adb_bin, *args],
            }
        if args[:1] == ["connect"]:
            return {"returncode": 0, "stdout": "connected", "stderr": "", "args": [self.adb_bin, *args]}
        if args[:1] == ["disconnect"]:
            return {"returncode": 0, "stdout": "disconnected", "stderr": "", "args": [self.adb_bin, *args]}
        return {"returncode": 1, "stdout": "", "stderr": "unsupported", "args": [self.adb_bin, *args]}


class AdbAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_wifi_setup_prefers_usb_when_serial_missing(self) -> None:
        adb = _StubAdbAdapter()
        adb.devices = [
            {"serial": "192.168.1.50:5555", "state": "device"},
            {"serial": "USB123", "state": "device"},
        ]

        result = await adb.wifi_setup(serial=None, port=5555)

        self.assertEqual(result.get("returncode"), 0)
        self.assertEqual(result.get("serial"), "USB123")
        self.assertEqual(result.get("endpoint"), "192.168.1.20:5555")
        self.assertIn(["-s", "USB123", "tcpip", "5555"], adb.calls)

    async def test_connect_normalizes_endpoint_without_port(self) -> None:
        adb = _StubAdbAdapter()
        result = await adb.connect(endpoint="192.168.1.20")
        self.assertEqual(result.get("returncode"), 0)
        self.assertIn(["connect", "192.168.1.20:5555"], adb.calls)

    async def test_wifi_setup_reports_no_available_device(self) -> None:
        adb = _StubAdbAdapter()
        adb.devices = []
        result = await adb.wifi_setup(serial=None, port=5555)
        self.assertNotEqual(result.get("returncode"), 0)
        self.assertIn("no authorized adb device", str(result.get("stderr", "")))


if __name__ == "__main__":
    unittest.main()
