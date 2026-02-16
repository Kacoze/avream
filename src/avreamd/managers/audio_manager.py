from __future__ import annotations

import asyncio
from typing import Any

from pathlib import Path
import json

from avreamd.api.errors import dependency_error
from avreamd.core.state_store import DaemonStateStore, SubsystemState
from avreamd.integrations.pactl import PactlIntegration
from avreamd.integrations.pipewire import PipeWireIntegration
from avreamd.managers.privilege_client import PrivilegeClient


class AudioManager:
    VIRTUAL_SINK_NAME = "avream_sink"
    VIRTUAL_SOURCE_NAME = "avream_mic"

    def __init__(
        self,
        *,
        state_store: DaemonStateStore,
        pipewire: PipeWireIntegration,
        pactl: PactlIntegration,
        privilege_client: PrivilegeClient,
        state_dir: Path,
    ) -> None:
        self._state_store = state_store
        self._pipewire = pipewire
        self._pactl = pactl
        self._privilege_client = privilege_client
        self._state_file = state_dir / "audio_state.json"
        self._lock = asyncio.Lock()
        self._active_backend = "none"
        self._native_loopback_process: asyncio.subprocess.Process | None = None
        self._scrcpy_route_task: asyncio.Task | None = None

    def _load_state(self) -> dict:
        try:
            return json.loads(self._state_file.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_state(self, data: dict) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def virtual_sink_name(self) -> str:
        return self.VIRTUAL_SINK_NAME

    def virtual_source_name(self) -> str:
        return self.VIRTUAL_SOURCE_NAME

    def _is_avream_pulse_module(self, module: dict[str, str]) -> bool:
        name = str(module.get("name", ""))
        args = str(module.get("args", ""))
        if name not in {"module-null-sink", "module-remap-source", "module-loopback"}:
            return False
        tokens = (
            f"sink_name={self.VIRTUAL_SINK_NAME}",
            f"source_name={self.VIRTUAL_SOURCE_NAME}",
            f"master={self.VIRTUAL_SINK_NAME}.monitor",
            f"sink={self.VIRTUAL_SINK_NAME}",
            "AVream Mic Bridge",
            "AVream Mic",
        )
        return any(token in args for token in tokens)

    def _cleanup_stale_pactl_modules(self) -> list[int]:
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

    async def _move_scrcpy_audio_to_virtual_sink(self, sink_name: str) -> dict[str, Any]:
        if not self._pactl.available:
            return {"moved": 0, "attempts": 0, "reason": "pactl_unavailable"}

        moved = 0
        attempts = 0
        last_error: str | None = None
        for _ in range(12):
            attempts += 1
            try:
                sink_inputs = self._pactl.list_sink_inputs_detailed()
            except Exception as exc:
                last_error = str(exc)
                await asyncio.sleep(0.2)
                continue

            scrcpy_ids: list[int] = []
            for entry in sink_inputs:
                sid_raw = entry.get("id")
                sid = int(sid_raw) if isinstance(sid_raw, str) and sid_raw.isdigit() else None
                if sid is None:
                    continue
                props = entry.get("properties")
                app_blob = ""
                if isinstance(props, dict):
                    app_blob = " ".join(
                        [
                            str(props.get("application.name", "")),
                            str(props.get("application.process.binary", "")),
                            str(props.get("media.name", "")),
                        ]
                    ).lower()
                if "scrcpy" in app_blob:
                    scrcpy_ids.append(sid)

            if not scrcpy_ids:
                await asyncio.sleep(0.2)
                continue

            for sid in scrcpy_ids:
                try:
                    self._pactl.move_sink_input(sid, sink_name)
                    moved += 1
                except Exception as exc:
                    last_error = str(exc)

            return {
                "moved": moved,
                "attempts": attempts,
                "matched": len(scrcpy_ids),
                "error": last_error,
            }

        return {"moved": moved, "attempts": attempts, "matched": 0, "error": last_error}

    def _start_scrcpy_route_task(self, sink_name: str) -> None:
        if self._scrcpy_route_task is not None:
            self._scrcpy_route_task.cancel()

        async def runner() -> None:
            while True:
                try:
                    if self._active_backend != "pipewire":
                        return
                    await self._move_scrcpy_audio_to_virtual_sink(sink_name)
                    await asyncio.sleep(0.8)
                except asyncio.CancelledError:
                    return
                except Exception:
                    await asyncio.sleep(1.0)

        self._scrcpy_route_task = asyncio.create_task(runner())

    async def start(self, backend: str = "pipewire") -> dict[str, Any]:
        async with self._lock:
            snapshot = await self._state_store.snapshot()
            state = snapshot["audio"]["state"]
            if state == SubsystemState.RUNNING.value:
                return {"state": "RUNNING", "already_running": True, "backend": self._active_backend}

            await self._state_store.transition_audio(SubsystemState.STARTING)
            selected = backend
            if backend == "pipewire":
                if self._pipewire.available() and self._pipewire.running():
                    selected = "pipewire"
                else:
                    selected = "snd_aloop"

            if selected == "pipewire":
                sink_name = self.VIRTUAL_SINK_NAME
                source_name = self.VIRTUAL_SOURCE_NAME
                if self._pactl.available:
                    removed = self._cleanup_stale_pactl_modules()
                    if removed:
                        self._save_state({"backend": "pipewire_cleanup", "removed_modules": removed})
                    # PipeWire via pulse compatibility modules.
                    sink_id: int | None = None
                    source_id: int | None = None
                    try:
                        sink_id = self._pactl.load_module(
                            "module-null-sink",
                            [
                                f"sink_name={sink_name}",
                                "sink_properties=device.description=Hidden_AVream_Bridge device.hidden=1",
                            ],
                        )
                        source_id = self._pactl.load_module(
                            "module-remap-source",
                            [
                                f"master={sink_name}.monitor",
                                f"source_name={source_name}",
                                "source_properties=device.description=AVream Mic",
                            ],
                        )
                    except Exception as exc:
                        # Roll back partial module setup.
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

                    move_result = await self._move_scrcpy_audio_to_virtual_sink(sink_name)
                    self._start_scrcpy_route_task(sink_name)
                    self._save_state({"backend": "pipewire", "modules": [sink_id, source_id], "move_result": move_result})
                elif self._pipewire.supports_native_virtual_mic():
                    # Native PipeWire fallback using pw-loopback process to expose a virtual source node.
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
                    self._save_state({"backend": "pipewire_native", "modules": []})
                else:
                    raise dependency_error(
                        "pipewire routing requires pactl or pw-loopback",
                        {
                            "tools": {"pactl": self._pactl.available, "pw_loopback": bool(self._pipewire.pw_loopback)},
                            "packages": ["pulseaudio-utils", "pipewire-bin"],
                        },
                    )

            if selected == "snd_aloop":
                await self._privilege_client.call("snd_aloop.load", {})
                self._save_state({"backend": "snd_aloop", "modules": []})

            self._active_backend = selected
            await self._state_store.transition_audio(SubsystemState.RUNNING)
            return {"state": "RUNNING", "already_running": False, "backend": selected}

    async def stop(self) -> dict[str, Any]:
        async with self._lock:
            snapshot = await self._state_store.snapshot()
            state = snapshot["audio"]["state"]
            if state == SubsystemState.STOPPED.value:
                return {"state": "STOPPED", "already_stopped": True}

            await self._state_store.transition_audio(SubsystemState.STOPPING)

            state = self._load_state()
            modules = state.get("modules", [])
            if isinstance(modules, list):
                for mid in modules:
                    try:
                        self._pactl.unload_module(int(mid))
                    except Exception:
                        pass
            # Also best-effort cleanup for stale modules not tracked in state file.
            self._cleanup_stale_pactl_modules()
            if state.get("backend") == "snd_aloop":
                try:
                    await self._privilege_client.call("snd_aloop.unload", {})
                except Exception:
                    pass
            if self._native_loopback_process is not None:
                try:
                    self._native_loopback_process.terminate()
                except Exception:
                    pass
                self._native_loopback_process = None
            if self._scrcpy_route_task is not None:
                self._scrcpy_route_task.cancel()
                self._scrcpy_route_task = None
            try:
                if self._state_file.exists():
                    self._state_file.unlink()
            except Exception:
                pass

            self._active_backend = "none"
            await self._state_store.transition_audio(SubsystemState.STOPPED)
            return {"state": "STOPPED", "already_stopped": False}
