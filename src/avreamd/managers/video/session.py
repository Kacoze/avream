from __future__ import annotations

import asyncio
from typing import Any

from avreamd.api.errors import conflict_error
from avreamd.backends.android_video import AndroidVideoBackend
from avreamd.core.process_supervisor import ProcessSupervisor
from avreamd.core.state_store import DaemonStateStore, InvalidTransitionError, SubsystemState
from avreamd.domain.models import VideoSource, VideoStartOptions
from avreamd.integrations.v4l2loopback import V4L2LoopbackIntegration


class VideoSessionService:
    PROC_NAME = "video-android"

    def __init__(
        self,
        *,
        state_store: DaemonStateStore,
        backend: AndroidVideoBackend,
        supervisor: ProcessSupervisor,
        v4l2: V4L2LoopbackIntegration,
        audio_manager: Any | None = None,
    ) -> None:
        self._state_store = state_store
        self._backend = backend
        self._supervisor = supervisor
        self._v4l2 = v4l2
        self._audio_manager = audio_manager
        self._active_source: VideoSource | None = None
        self._active_proc_name: str | None = None

    @property
    def active_source(self) -> dict[str, Any] | None:
        if self._active_source is None:
            return None
        return self._active_source.as_dict()

    @property
    def active_process(self) -> str | None:
        return self._active_proc_name

    def clear_active(self) -> None:
        self._active_source = None
        self._active_proc_name = None

    async def list_sources(self) -> list[dict[str, str]]:
        return await self._backend.list_sources()

    async def start(self, *, options: VideoStartOptions) -> dict[str, Any]:
        snapshot = await self._state_store.snapshot()
        current = snapshot["video"]["state"]
        running = self._supervisor.running(self.PROC_NAME)

        if current in {SubsystemState.RUNNING.value, SubsystemState.STARTING.value} and running:
            return {
                "state": "RUNNING",
                "already_running": True,
                "source": self.active_source,
            }

        if current == SubsystemState.STOPPING.value and running:
            raise conflict_error("video is stopping; retry in a moment", {"state": current})

        if not running and current in {SubsystemState.RUNNING.value, SubsystemState.STARTING.value}:
            await self._state_store.transition_video(SubsystemState.STOPPING)
            await self._state_store.transition_video(SubsystemState.STOPPED)
            self.clear_active()

        try:
            await self._state_store.transition_video(SubsystemState.STARTING)
        except InvalidTransitionError as exc:
            raise conflict_error("video start is not allowed in current state", {"state": current}) from exc

        source_obj = await self._backend.select_default_source(preferred_serial=options.serial)
        command = self._backend.build_start_command(
            serial=source_obj.serial,
            sink_path=str(self._v4l2.device_path),
            preset=options.preset,
            camera_facing=options.camera_facing,
            camera_rotation=options.camera_rotation,
            preview_window=options.preview_window,
            enable_audio=options.enable_audio,
        )

        managed = await self._supervisor.start(self.PROC_NAME, command)
        await asyncio.sleep(0.2)
        if managed.process.returncode is not None:
            await self._state_store.set_video_error(
                "E_BACKEND_FAILED",
                "android backend exited immediately",
                {
                    "returncode": managed.process.returncode,
                    "command": command,
                },
            )
            raise conflict_error("failed to start android backend", {"returncode": managed.process.returncode})

        await self._state_store.transition_video(SubsystemState.RUNNING)
        self._active_source = VideoSource(
            serial=source_obj.serial,
            camera_facing=options.camera_facing,
            camera_rotation=options.camera_rotation,
            preview_window=options.preview_window,
        )
        self._active_proc_name = self.PROC_NAME

        audio_result: dict[str, Any] | None = None
        if self._audio_manager is not None:
            try:
                audio_result = await self._audio_manager.start(backend="pipewire")
            except Exception as exc:  # pragma: no cover - defensive
                audio_result = {
                    "state": "ERROR",
                    "already_running": False,
                    "backend": "pipewire",
                    "error": str(exc),
                }

        result = {
            "state": "RUNNING",
            "already_running": False,
            "source": self.active_source,
        }
        if audio_result is not None:
            result["audio"] = audio_result
        return result

    async def stop(self) -> dict[str, Any]:
        snapshot = await self._state_store.snapshot()
        current = snapshot["video"]["state"]
        running = self._supervisor.running(self.PROC_NAME)

        if current == SubsystemState.STOPPED.value and not running:
            return {"state": "STOPPED", "already_stopped": True}

        if current != SubsystemState.STOPPING.value:
            await self._state_store.transition_video(SubsystemState.STOPPING)

        await self._supervisor.stop(self.PROC_NAME)
        await self._state_store.transition_video(SubsystemState.STOPPED)
        self.clear_active()

        audio_result: dict[str, Any] | None = None
        if self._audio_manager is not None:
            try:
                audio_result = await self._audio_manager.stop()
            except Exception as exc:  # pragma: no cover - defensive
                audio_result = {
                    "state": "ERROR",
                    "already_stopped": False,
                    "error": str(exc),
                }

        result = {"state": "STOPPED", "already_stopped": False}
        if audio_result is not None:
            result["audio"] = audio_result
        return result
