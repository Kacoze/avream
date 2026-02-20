from __future__ import annotations

import asyncio
import ipaddress
import os
import re
import shutil

from avreamd.domain.models import AdbCommandResult
from avreamd.integrations.command_runner import CommandRunner


class AdbAdapter:
    def __init__(self, adb_bin: str | None = None) -> None:
        env_bin = os.getenv("AVREAM_ADB_BIN")
        self.adb_bin = adb_bin or env_bin or shutil.which("adb")
        self._runner = CommandRunner()
        self._adb_lock = asyncio.Lock()

    @property
    def available(self) -> bool:
        return bool(self.adb_bin)

    async def list_devices(self) -> list[dict[str, str]]:
        if not self.adb_bin:
            return []

        result = await self._run(["devices"])
        if self._as_int(result.get("returncode"), 1) != 0:
            return []

        devices: list[dict[str, str]] = []
        stdout = str(result.get("stdout", ""))
        for line in stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("List of devices"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                devices.append({"serial": parts[0], "state": parts[1]})
        return devices

    async def tcpip(self, *, serial: str, port: int = 5555) -> dict[str, object]:
        return await self._run(["-s", serial, "tcpip", str(int(port))])

    async def connect(self, *, endpoint: str) -> dict[str, object]:
        normalized = self.normalize_endpoint(endpoint)
        return await self._run(["connect", normalized])

    async def disconnect(self, *, endpoint: str) -> dict[str, object]:
        normalized = self.normalize_endpoint(endpoint)
        return await self._run(["disconnect", normalized])

    async def connect_with_retry(self, *, endpoint: str, retries: int = 3, backoff_base_s: float = 0.5) -> dict[str, object]:
        normalized = self.normalize_endpoint(endpoint)
        attempts = max(1, int(retries))
        last: dict[str, object] = {
            "returncode": 1,
            "stdout": "",
            "stderr": "unknown error",
            "args": [self.adb_bin or "adb", "connect", normalized],
        }
        for i in range(1, attempts + 1):
            last = await self.connect(endpoint=normalized)
            if self._as_int(last.get("returncode"), 1) == 0:
                last["attempt"] = i
                last["attempts"] = attempts
                return last
            if i < attempts:
                await asyncio.sleep(backoff_base_s * i)
        last["attempt"] = attempts
        last["attempts"] = attempts
        return last

    async def detect_device_ip(self, *, serial: str) -> str | None:
        for iface in ("wlan0", "swlan0", "wlan1", "wlan2", "wifi0"):
            res = await self._run(["-s", serial, "shell", "ip", "-4", "-o", "addr", "show", iface])
            if self._as_int(res.get("returncode"), 1) != 0:
                continue
            ip = self._extract_ipv4_from_text(str(res.get("stdout", "")))
            if ip:
                return ip

        res = await self._run(["-s", serial, "shell", "ip", "-4", "-o", "addr", "show"])
        if self._as_int(res.get("returncode"), 1) != 0:
            return None

        private_candidate: str | None = None
        first_candidate: str | None = None
        for line in str(res.get("stdout", "")).splitlines():
            line = line.strip()
            if not line:
                continue
            if " lo " in f" {line} ":
                continue
            ip = self._extract_ipv4_from_text(line)
            if not ip:
                continue
            if first_candidate is None:
                first_candidate = ip
            try:
                addr = ipaddress.ip_address(ip)
                if addr.is_private:
                    private_candidate = ip
                    break
            except ValueError:
                continue

        return private_candidate or first_candidate

    async def wifi_setup(self, *, serial: str | None = None, port: int = 5555) -> dict[str, object]:
        if not self.adb_bin:
            return {"returncode": 127, "stdout": "", "stderr": "adb not found"}

        target_serial = serial
        devices = await self.list_devices()
        if not target_serial:
            for dev in devices:
                dev_serial = str(dev.get("serial", ""))
                if dev.get("state") == "device" and self.transport_of(dev_serial) == "usb":
                    target_serial = dev_serial
                    break
        if not target_serial:
            for dev in devices:
                if dev.get("state") == "device":
                    target_serial = str(dev.get("serial", ""))
                    break

        if not target_serial:
            return {
                "returncode": 2,
                "stdout": "",
                "stderr": "no authorized adb device available",
                "devices": devices,
            }

        tcp = await self.tcpip(serial=target_serial, port=port)
        if self._as_int(tcp.get("returncode"), 1) != 0:
            return {
                "returncode": self._as_int(tcp.get("returncode"), 1),
                "stdout": str(tcp.get("stdout", "")),
                "stderr": str(tcp.get("stderr", "failed to enable tcpip")),
                "serial": target_serial,
                "port": int(port),
                "tcpip": tcp,
            }

        ip: str | None = None
        # After switching to tcpip, adbd may restart and briefly report device offline.
        for attempt in range(1, 13):
            ip = await self.detect_device_ip(serial=target_serial)
            if ip:
                break
            await asyncio.sleep(0.5)
        if not ip:
            return {
                "returncode": 3,
                "stdout": str(tcp.get("stdout", "")),
                "stderr": "failed to detect device Wi-Fi IP over ADB (keep phone unlocked and USB connected during setup)",
                "serial": target_serial,
                "port": int(port),
                "tcpip": tcp,
            }

        endpoint = f"{ip}:{int(port)}"
        conn = await self.connect_with_retry(endpoint=endpoint, retries=3, backoff_base_s=0.5)
        return {
            "returncode": self._as_int(conn.get("returncode"), 1),
            "serial": target_serial,
            "ip": ip,
            "port": int(port),
            "endpoint": endpoint,
            "tcpip": tcp,
            "connect": conn,
            "stdout": str(conn.get("stdout", "")),
            "stderr": str(conn.get("stderr", "")),
            "devices": devices,
        }

    async def get_device_property(self, *, serial: str, prop: str) -> str | None:
        res = await self._run(["-s", serial, "shell", "getprop", prop])
        if self._as_int(res.get("returncode"), 1) != 0:
            return None
        value = str(res.get("stdout", "")).strip()
        if not value:
            return None
        if value.lower() == "unknown":
            return None
        return value

    async def device_identity(self, *, serial: str) -> str | None:
        # Stable physical-device key for deduping USB+Wi-Fi adb entries.
        for prop in ("ro.serialno", "ro.boot.serialno"):
            value = await self.get_device_property(serial=serial, prop=prop)
            if value:
                return value
        return None

    async def _run(self, args: list[str]) -> dict[str, object]:
        if not self.adb_bin:
            return {"returncode": 127, "stdout": "", "stderr": "adb not found"}

        async with self._adb_lock:
            result = await self._runner.run_async([self.adb_bin, *args])
        result = AdbCommandResult(
            returncode=int(result.returncode),
            stdout=result.stdout,
            stderr=result.stderr,
            args=result.args,
        )
        return result.as_dict()

    @staticmethod
    def transport_of(serial: str) -> str:
        return "wifi" if ":" in serial else "usb"

    @staticmethod
    def normalize_endpoint(endpoint: str, default_port: int = 5555) -> str:
        text = (endpoint or "").strip()
        if not text:
            return text
        if ":" in text:
            return text
        return f"{text}:{int(default_port)}"

    @staticmethod
    def _extract_ipv4_from_text(text: str) -> str | None:
        m = re.search(r"\b(\d{1,3}(?:\.\d{1,3}){3})/\d+\b", text)
        if not m:
            return None
        candidate = m.group(1)
        try:
            ipaddress.ip_address(candidate)
        except ValueError:
            return None
        return candidate

    @staticmethod
    def _as_int(value: object, default: int) -> int:
        try:
            if isinstance(value, int):
                return value
            if isinstance(value, (str, float, bool)):
                return int(value)
            return int(default)
        except Exception:
            return int(default)
