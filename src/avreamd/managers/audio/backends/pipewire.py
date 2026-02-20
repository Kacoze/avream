from __future__ import annotations

import asyncio
from typing import Any

from avreamd.api.errors import dependency_error
from avreamd.integrations.pactl import PactlIntegration
from avreamd.integrations.pipewire import PipeWireIntegration
from avreamd.managers.audio.routing.scrcpy_router import ScrcpyAudioRouter


class PipeWireAudioBackend:
    def __init__(
        self,
        *,
        pipewire: PipeWireIntegration,
        pactl: PactlIntegration,
        sink_name: str,
        source_name: str,
    ) -> None:
        self._pipewire = pipewire
        self._pactl = pactl
        self._sink_name = sink_name
        self._source_name = source_name
        self._native_loopback_process: asyncio.subprocess.Process | None = None
        self._router = ScrcpyAudioRouter(pactl=pactl, sink_name=sink_name)

    def _is_avream_pulse_module(self, module: dict[str, str]) -> bool:
        name = str(module.get("name", ""))
        args = str(module.get("args", ""))
        if name not in {"module-null-sink", "module-remap-source", "module-loopback"}:
            return False
        tokens = (
            f"sink_name={self._sink_name}",
            f"source_name={self._source_name}",
            f"master={self._sink_name}.monitor",
            f"sink={self._sink_name}",
            "AVream Mic Bridge",
            "AVream Mic",
        )
        return any(token in args for token in tokens)

    def cleanup_stale_pactl_modules(self) -> list[int]:
        if not self._pactl.available:
            return []
        removed: list[int] = []
        try:
            modules = self._pactl.list_modules()
        except Exception:
            return []

        for mod in modules:
            if not self._is_avream_pulse_module(mod):
                continue
            module_id_str = str(mod.get("id", "")).strip()
            if not module_id_str.isdigit():
                continue
            module_id = int(module_id_str)
            try:
                self._pactl.unload_module(module_id)
                removed.append(module_id)
            except Exception:
                continue
        return removed

    async def start(self, *, is_active) -> dict[str, Any]:
        if self._pactl.available:
            sink_id: int | None = None
            source_id: int | None = None
            try:
                sink_id = self._pactl.load_module(
                    "module-null-sink",
                    [
                        f"sink_name={self._sink_name}",
                        "sink_properties=device.description=Hidden_AVream_Bridge device.hidden=1",
                    ],
                )
                source_id = self._pactl.load_module(
                    "module-remap-source",
                    [
                        f"master={self._sink_name}.monitor",
                        f"source_name={self._source_name}",
                        "source_properties=device.description=AVream Mic",
                    ],
                )
            except Exception as exc:
                if source_id is not None:
                    try:
                        self._pactl.unload_module(int(source_id))
                    except Exception:
                        pass
                if sink_id is not None:
                    try:
                        self._pactl.unload_module(int(sink_id))
                    except Exception:
                        pass
                raise dependency_error(
                    "failed to create virtual mic via pactl",
                    {"tool": "pactl", "package": "pulseaudio-utils", "error": str(exc)},
                )

            move_result = await self._router.move_once()
            self._router.start_background(is_active=is_active)
            return {"backend": "pipewire", "modules": [sink_id, source_id], "move_result": move_result}

        if self._pipewire.supports_native_virtual_mic():
            assert self._pipewire.pw_loopback is not None
            cmd = [
                self._pipewire.pw_loopback,
                "--capture-props",
                "{ node.name=\"avream_sink\" node.description=\"AVream Sink\" media.class=\"Audio/Sink\" }",
                "--playback-props",
                "{ node.name=\"avream_mic\" node.description=\"AVream Mic\" media.class=\"Audio/Source\" }",
            ]
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
            except Exception as exc:
                raise dependency_error(
                    "failed to start pw-loopback",
                    {"tool": "pw-loopback", "package": "pipewire-bin", "error": str(exc)},
                )
            if proc.returncode is not None and proc.returncode != 0:
                raise dependency_error(
                    "pw-loopback exited immediately",
                    {"tool": "pw-loopback", "package": "pipewire-bin", "returncode": proc.returncode},
                )
            self._native_loopback_process = proc
            return {"backend": "pipewire_native", "modules": []}

        raise dependency_error(
            "pipewire routing requires pactl or pw-loopback",
            {
                "tools": {"pactl": self._pactl.available, "pw_loopback": bool(self._pipewire.pw_loopback)},
                "packages": ["pulseaudio-utils", "pipewire-bin"],
            },
        )

    async def stop(self, *, state: dict[str, Any]) -> None:
        modules = state.get("modules", [])
        if isinstance(modules, list):
            for mid in modules:
                try:
                    self._pactl.unload_module(int(mid))
                except Exception:
                    pass
        self.cleanup_stale_pactl_modules()
        if self._native_loopback_process is not None:
            try:
                self._native_loopback_process.terminate()
            except Exception:
                pass
            self._native_loopback_process = None
        self._router.stop_background()
