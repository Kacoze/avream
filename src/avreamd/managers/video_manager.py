from __future__ import annotations

import asyncio
from typing import Any

from avreamd.api.errors import conflict_error
from avreamd.backends.android_video import AndroidVideoBackend
from avreamd.core.process_supervisor import ProcessSupervisor
from avreamd.core.state_store import DaemonStateStore, InvalidTransitionError, SubsystemState
from avreamd.domain.models import ReconnectPolicy, VideoStartOptions
from avreamd.integrations.v4l2loopback import V4L2LoopbackIntegration
from avreamd.managers.privilege_client import PrivilegeClient
from avreamd.managers.video import VideoDeviceResetService, VideoReconnectController, VideoSessionService


class VideoManager:
    PROC_NAME = "video-android"

    def __init__(
        self,
        *,
        state_store: DaemonStateStore,
        backend: AndroidVideoBackend,
        supervisor: ProcessSupervisor,
        privilege_client: PrivilegeClient,
        v4l2: V4L2LoopbackIntegration,
        audio_manager=None,
    ) -> None:
        self._state_store = state_store
        self._supervisor = supervisor
        self._lock = asyncio.Lock()
        self._session = VideoSessionService(
            state_store=state_store,
            backend=backend,
            supervisor=supervisor,
            v4l2=v4l2,
            audio_manager=audio_manager,
        )
        self._device_reset = VideoDeviceResetService(privilege_client=privilege_client, v4l2=v4l2)
        self._reconnect = VideoReconnectController(
            state_store=state_store,
            supervisor=supervisor,
            proc_name=self.PROC_NAME,
        )
        self._camera_facing = "front"
        self._camera_rotation = 0
        self._preview_window = False
        self._reconnect_cfg: dict[str, Any] = {"enabled": True, "max_attempts": 3, "backoff_ms": 1500}

    async def runtime_status(self) -> dict[str, Any]:
        last_exit = self._supervisor.last_exit_code(self.PROC_NAME)
        return {
            "active_source": self._session.active_source,
            "active_process": self._session.active_process,
            "last_exit_code": last_exit,
            "reconnect": self._reconnect.runtime_status(),
            "log_pointers": {
                "video_android": self._supervisor.latest_log_path(self.PROC_NAME),
            },
        }

    async def stop_reconnect(self) -> dict[str, Any]:
        async with self._lock:
            self._reconnect.cancel(state="stopped")
            return {"stopped": True, "reconnect": self._reconnect.runtime_status()}

    async def list_sources(self) -> list[dict[str, str]]:
        return await self._session.list_sources()

    def _policy_from_cfg(self) -> ReconnectPolicy:
        return ReconnectPolicy(
            enabled=bool(self._reconnect_cfg.get("enabled", True)),
            max_attempts=int(self._reconnect_cfg.get("max_attempts", 3) or 3),
            backoff_ms=int(self._reconnect_cfg.get("backoff_ms", 1500) or 1500),
        ).normalized()

    async def start(
        self,
        reconnect: bool = False,
        serial: str | None = None,
        camera_facing: str | None = None,
        camera_rotation: int | None = None,
        preview_window: bool | None = None,
    ) -> dict[str, Any]:
        async with self._lock:
            facing = camera_facing if camera_facing in {"front", "back"} else self._camera_facing
            rotation = camera_rotation if camera_rotation in {0, 90, 180, 270} else self._camera_rotation
            window = bool(preview_window) if preview_window is not None else self._preview_window

            self._reconnect.configure(self._policy_from_cfg())
            await self._device_reset.ensure_ready()

            result = await self._session.start(
                options=VideoStartOptions(
                    serial=serial,
                    camera_facing=facing,
                    camera_rotation=rotation,
                    preview_window=window,
                    enable_audio=True,
                    preset="balanced",
                )
            )

            self._camera_facing = facing
            self._camera_rotation = rotation
            self._preview_window = window

            if not reconnect:
                self._reconnect.start_watch(on_restart=self._restart_from_watch, on_exhausted=self._on_exhausted_retries)

            return result

    async def _restart_from_watch(self) -> None:
        serial = None
        active = self._session.active_source
        if isinstance(active, dict):
            source_serial = active.get("serial")
            if isinstance(source_serial, str) and source_serial:
                serial = source_serial
        await self.start(
            reconnect=True,
            serial=serial,
            camera_facing=self._camera_facing,
            camera_rotation=self._camera_rotation,
            preview_window=self._preview_window,
        )

    async def _on_exhausted_retries(self, rc: int | None, max_attempts: int) -> None:
        await self._state_store.set_video_error(
            "E_BACKEND_FAILED",
            "video backend exited and reconnect attempts exhausted",
            {"returncode": rc, "attempts": max_attempts},
        )

    async def stop(self) -> dict[str, Any]:
        async with self._lock:
            self._reconnect.cancel(state="idle")
            result = await self._session.stop()
            await asyncio.sleep(2.0)
            result["post_stop_reset"] = await self._device_reset.best_effort_reload_after_stop()
            return result

    async def reset(self, force: bool = False) -> dict[str, Any]:
        async with self._lock:
            return await self._reset_unlocked(force=force)

    async def _reset_unlocked(self, force: bool = False) -> dict[str, Any]:
        running = self._supervisor.running(self.PROC_NAME)
        if running:
            self._reconnect.cancel(state="idle")

            snap = await self._state_store.snapshot()
            current = snap["video"]["state"]
            if current != SubsystemState.STOPPING.value:
                try:
                    await self._state_store.transition_video(SubsystemState.STOPPING)
                except InvalidTransitionError:
                    pass

            await self._supervisor.stop(self.PROC_NAME)

            snap_after = await self._state_store.snapshot()
            if snap_after["video"]["state"] != SubsystemState.STOPPED.value:
                try:
                    await self._state_store.transition_video(SubsystemState.STOPPED)
                except InvalidTransitionError:
                    pass

            self._session.clear_active()

        return await self._device_reset.reset(force=force)
