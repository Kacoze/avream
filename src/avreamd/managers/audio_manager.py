from __future__ import annotations

import asyncio
from pathlib import Path

from avreamd.api.errors import dependency_error
from avreamd.core.state_store import DaemonStateStore, SubsystemState
from avreamd.integrations.pactl import PactlIntegration
from avreamd.integrations.pipewire import PipeWireIntegration
from avreamd.managers.audio import AudioStateRepository, PipeWireAudioBackend, SndAloopAudioBackend
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
        self._lock = asyncio.Lock()
        self._active_backend = "none"
        self._state_repo = AudioStateRepository(state_file=state_dir / "audio_state.json")
        self._pipewire_backend = PipeWireAudioBackend(
            pipewire=pipewire,
            pactl=pactl,
            sink_name=self.VIRTUAL_SINK_NAME,
            source_name=self.VIRTUAL_SOURCE_NAME,
        )
        self._snd_aloop_backend = SndAloopAudioBackend(privilege_client=privilege_client)

    def virtual_sink_name(self) -> str:
        return self.VIRTUAL_SINK_NAME

    def virtual_source_name(self) -> str:
        return self.VIRTUAL_SOURCE_NAME

    async def start(self, backend: str = "pipewire") -> dict[str, object]:
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
                removed = self._pipewire_backend.cleanup_stale_pactl_modules()
                if removed:
                    self._state_repo.save({"backend": "pipewire_cleanup", "removed_modules": removed})
                payload = await self._pipewire_backend.start(is_active=lambda: self._active_backend == "pipewire")
                self._state_repo.save(payload)

            if selected == "snd_aloop":
                await self._snd_aloop_backend.start()
                self._state_repo.save({"backend": "snd_aloop", "modules": []})

            if selected not in {"pipewire", "snd_aloop"}:
                raise dependency_error("unsupported audio backend", {"backend": selected})

            self._active_backend = selected
            await self._state_store.transition_audio(SubsystemState.RUNNING)
            return {"state": "RUNNING", "already_running": False, "backend": selected}

    async def stop(self) -> dict[str, object]:
        async with self._lock:
            snapshot = await self._state_store.snapshot()
            state = snapshot["audio"]["state"]
            if state == SubsystemState.STOPPED.value:
                return {"state": "STOPPED", "already_stopped": True}

            await self._state_store.transition_audio(SubsystemState.STOPPING)

            state_data = self._state_repo.load()
            backend_name = str(state_data.get("backend", ""))
            if backend_name in {"pipewire", "pipewire_native", "pipewire_cleanup"}:
                await self._pipewire_backend.stop(state=state_data)
            if backend_name == "snd_aloop":
                await self._snd_aloop_backend.stop()

            self._state_repo.clear()
            self._active_backend = "none"
            await self._state_store.transition_audio(SubsystemState.STOPPED)
            return {"state": "STOPPED", "already_stopped": False}
