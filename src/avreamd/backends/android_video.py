from __future__ import annotations

from dataclasses import dataclass

from avreamd.api.errors import backend_error, dependency_error
from avreamd.integrations.adb import AdbAdapter
from avreamd.integrations.scrcpy import ScrcpyAdapter


@dataclass
class AndroidSource:
    serial: str
    state: str


class AndroidVideoBackend:
    def __init__(self, adb: AdbAdapter, scrcpy: ScrcpyAdapter) -> None:
        self.adb = adb
        self.scrcpy = scrcpy

    async def list_sources(self) -> list[dict[str, str]]:
        devices = await self.adb.list_devices()
        return [{"type": "android", **d} for d in devices]

    async def select_default_source(
        self,
        preferred_serial: str | None = None,
        preferred_transport: str | None = None,
    ) -> AndroidSource:
        if not self.adb.available:
            raise dependency_error("adb is missing", {"tool": "adb", "package": "android-tools-adb"})
        devices = await self.adb.list_devices()

        # Explicit device selection first.
        if preferred_serial:
            matched = [d for d in devices if d.get("serial") == preferred_serial]
            if matched:
                dev = matched[0]
                if dev.get("state") == "device":
                    return AndroidSource(serial=dev["serial"], state=dev["state"])
                raise backend_error(
                    "preferred Android device is not authorized/ready",
                    {"serial": preferred_serial, "state": dev.get("state"), "devices": devices},
                    retryable=True,
                )

        # Then transport preference (usb/wifi) among healthy devices.
        if preferred_transport in {"usb", "wifi"}:
            for dev in devices:
                serial = dev.get("serial", "")
                if dev.get("state") == "device" and self.adb.transport_of(serial) == preferred_transport:
                    return AndroidSource(serial=dev["serial"], state=dev["state"])

        # Finally any healthy device.
        for dev in devices:
            if dev.get("state") == "device":
                return AndroidSource(serial=dev["serial"], state=dev["state"])
        raise backend_error("no authorized Android device available", {"devices": devices}, retryable=True)

    def build_start_command(
        self,
        *,
        serial: str,
        sink_path: str,
        preset: str = "balanced",
        camera_facing: str | None = None,
        preview_window: bool = False,
        enable_audio: bool = False,
    ) -> list[str]:
        if not self.scrcpy.available:
            raise dependency_error("scrcpy is missing", {"tool": "scrcpy", "package": "scrcpy"})
        return self.scrcpy.command_for_android_camera(
            serial=serial,
            sink_path=sink_path,
            preset=preset,
            camera_facing=camera_facing,
            preview_window=preview_window,
            enable_audio=enable_audio,
            extra_args=None,
        )
