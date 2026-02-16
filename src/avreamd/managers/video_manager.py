from __future__ import annotations

import asyncio
import time
from typing import Any

from avreamd.api.errors import ApiError, busy_device_error, conflict_error
from avreamd.backends.android_video import AndroidVideoBackend
from avreamd.core.process_supervisor import ProcessSupervisor
from avreamd.core.state_store import DaemonStateStore, InvalidTransitionError, SubsystemState
from avreamd.integrations.v4l2loopback import V4L2LoopbackIntegration
from avreamd.managers.privilege_client import PrivilegeClient


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
        self._backend = backend
        self._supervisor = supervisor
        self._privilege_client = privilege_client
        self._v4l2 = v4l2
        self._audio_manager = audio_manager
        self._lock = asyncio.Lock()
        self._active_source: dict[str, Any] | None = None
        self._watch_task: asyncio.Task | None = None
        self._active_proc_name: str | None = None
        self._camera_facing = "front"
        self._camera_rotation = 0
        self._preview_window = False
        self._reconnect_cfg: dict[str, Any] = {"enabled": True, "max_attempts": 3, "backoff_ms": 1500}
        self._reconnect_status: dict[str, Any] = {
            "enabled": True,
            "state": "idle",
            "attempt": 0,
            "max_attempts": 3,
            "backoff_ms": 1500,
            "next_retry_in_ms": None,
            "last_exit_code": None,
        }

    async def runtime_status(self) -> dict[str, Any]:
        last_exit = self._supervisor.last_exit_code(self.PROC_NAME)
        return {
            "active_source": self._active_source,
            "active_process": self._active_proc_name,
            "last_exit_code": last_exit,
            "reconnect": dict(self._reconnect_status),
            "log_pointers": {
                "video_android": self._supervisor.latest_log_path(self.PROC_NAME),
            },
        }

    async def stop_reconnect(self) -> dict[str, Any]:
        async with self._lock:
            if self._watch_task is not None:
                self._watch_task.cancel()
                self._watch_task = None
            self._reconnect_status["state"] = "stopped"
            self._reconnect_status["attempt"] = 0
            self._reconnect_status["next_retry_in_ms"] = None
            return {"stopped": True, "reconnect": dict(self._reconnect_status)}

    async def list_sources(self) -> list[dict[str, str]]:
        return await self._backend.list_sources()

    async def start(
        self,
        reconnect: bool = False,
        serial: str | None = None,
        camera_facing: str | None = None,
        camera_rotation: int | None = None,
        preview_window: bool | None = None,
    ) -> dict[str, Any]:
        async with self._lock:
            snapshot = await self._state_store.snapshot()
            current = snapshot["video"]["state"]
            running = self._supervisor.running(self.PROC_NAME)

            if current in {SubsystemState.RUNNING.value, SubsystemState.STARTING.value} and running:
                return {
                    "state": "RUNNING",
                    "already_running": True,
                    "source": self._active_source,
                }

            if current == SubsystemState.STOPPING.value and running:
                raise conflict_error("video is stopping; retry in a moment", {"state": current})

            if not running and current in {SubsystemState.RUNNING.value, SubsystemState.STARTING.value}:
                await self._state_store.transition_video(SubsystemState.STOPPING)
                await self._state_store.transition_video(SubsystemState.STOPPED)
                self._active_proc_name = None
                self._active_source = None

            try:
                await self._state_store.transition_video(SubsystemState.STARTING)
            except InvalidTransitionError as exc:
                raise conflict_error("video start is not allowed in current state", {"state": current}) from exc

            enabled = bool(self._reconnect_cfg.get("enabled", True))
            max_attempts = int(self._reconnect_cfg.get("max_attempts", 3) or 3)
            backoff_ms = int(self._reconnect_cfg.get("backoff_ms", 1500) or 1500)
            self._reconnect_status.update(
                {
                    "enabled": enabled,
                    "state": "idle",
                    "attempt": 0,
                    "max_attempts": max(0, min(max_attempts, 20)) if enabled else 0,
                    "backoff_ms": max(100, min(backoff_ms, 60000)) if enabled else 0,
                    "next_retry_in_ms": None,
                }
            )

            await self._ensure_v4l2_ready_unlocked()

            source_obj = await self._backend.select_default_source(preferred_serial=serial)
            facing = camera_facing if camera_facing in {"front", "back"} else self._camera_facing
            rotation = camera_rotation if camera_rotation in {0, 90, 180, 270} else self._camera_rotation
            window = bool(preview_window) if preview_window is not None else self._preview_window
            command = self._backend.build_start_command(
                serial=source_obj.serial,
                sink_path=str(self._v4l2.device_path),
                preset="balanced",
                camera_facing=facing,
                camera_rotation=rotation,
                preview_window=window,
                enable_audio=True,
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
            self._camera_facing = facing
            self._camera_rotation = rotation
            self._preview_window = window
            self._active_source = {
                "type": "android",
                "serial": source_obj.serial,
                "camera_facing": facing,
                "camera_rotation": rotation,
                "preview_window": window,
            }
            self._active_proc_name = self.PROC_NAME

            audio_result: dict[str, Any] | None = None
            if self._audio_manager is not None:
                try:
                    audio_result = await self._audio_manager.start(backend="pipewire")
                except Exception as exc:
                    audio_result = {
                        "state": "ERROR",
                        "already_running": False,
                        "backend": "pipewire",
                        "error": str(exc),
                    }

            if not reconnect:
                self._start_watch_task_unlocked()

            result = {
                "state": "RUNNING",
                "already_running": False,
                "source": self._active_source,
            }
            if audio_result is not None:
                result["audio"] = audio_result
            return result

    async def stop(self) -> dict[str, Any]:
        async with self._lock:
            snapshot = await self._state_store.snapshot()
            current = snapshot["video"]["state"]
            running = self._supervisor.running(self.PROC_NAME)

            if current == SubsystemState.STOPPED.value and not running:
                return {"state": "STOPPED", "already_stopped": True}

            if self._watch_task is not None:
                self._watch_task.cancel()
                self._watch_task = None
            self._reconnect_status.update({"state": "idle", "attempt": 0, "next_retry_in_ms": None})

            if current != SubsystemState.STOPPING.value:
                await self._state_store.transition_video(SubsystemState.STOPPING)

            await self._supervisor.stop(self.PROC_NAME)
            await self._state_store.transition_video(SubsystemState.STOPPED)
            await asyncio.sleep(2.0)
            post_stop_reset = await self._best_effort_reload_after_stop_unlocked()
            self._active_source = None
            self._active_proc_name = None

            audio_result: dict[str, Any] | None = None
            if self._audio_manager is not None:
                try:
                    audio_result = await self._audio_manager.stop()
                except Exception as exc:
                    audio_result = {
                        "state": "ERROR",
                        "already_stopped": False,
                        "error": str(exc),
                    }

            result = {"state": "STOPPED", "already_stopped": False, "post_stop_reset": post_stop_reset}
            if audio_result is not None:
                result["audio"] = audio_result
            return result

    def _start_watch_task_unlocked(self) -> None:
        if self._watch_task is not None:
            self._watch_task.cancel()

        async def watch() -> None:
            while True:
                try:
                    rc = await self._supervisor.wait(self.PROC_NAME)
                except Exception:
                    return

                enabled = bool(self._reconnect_cfg.get("enabled", False))
                max_attempts = int(self._reconnect_cfg.get("max_attempts", 3) or 3)
                backoff_ms = int(self._reconnect_cfg.get("backoff_ms", 1500) or 1500)
                if not enabled:
                    return

                self._reconnect_status.update(
                    {
                        "enabled": True,
                        "max_attempts": max_attempts,
                        "backoff_ms": backoff_ms,
                        "last_exit_code": rc,
                        "state": "exited",
                        "attempt": 0,
                        "next_retry_in_ms": None,
                    }
                )

                snap = await self._state_store.snapshot()
                if snap["video"]["state"] != SubsystemState.RUNNING.value:
                    return

                attempt = 0
                while attempt < max_attempts:
                    attempt += 1
                    self._reconnect_status["attempt"] = attempt
                    self._reconnect_status["state"] = "waiting"
                    next_at = time.monotonic() + (backoff_ms / 1000.0)
                    self._reconnect_status["next_retry_in_ms"] = int(backoff_ms)
                    await asyncio.sleep(backoff_ms / 1000.0)
                    if time.monotonic() >= next_at:
                        self._reconnect_status["next_retry_in_ms"] = 0

                    snap = await self._state_store.snapshot()
                    if snap["video"]["state"] != SubsystemState.RUNNING.value:
                        return

                    try:
                        await self._state_store.transition_video(SubsystemState.STARTING)
                    except Exception:
                        pass
                    try:
                        self._reconnect_status["state"] = "restarting"
                        serial = None
                        if isinstance(self._active_source, dict):
                            source_serial = self._active_source.get("serial")
                            if isinstance(source_serial, str) and source_serial:
                                serial = source_serial
                        await self.start(
                            reconnect=True,
                            serial=serial,
                            camera_facing=self._camera_facing,
                            camera_rotation=self._camera_rotation,
                            preview_window=self._preview_window,
                        )
                        self._reconnect_status.update({"state": "running", "attempt": 0, "next_retry_in_ms": None})
                        break
                    except Exception:
                        try:
                            await self._state_store.transition_video(SubsystemState.RUNNING)
                        except Exception:
                            pass
                        self._reconnect_status["state"] = "failed"
                        continue
                else:
                    self._reconnect_status.update({"state": "exhausted", "next_retry_in_ms": None})
                    await self._state_store.set_video_error(
                        "E_BACKEND_FAILED",
                        "video backend exited and reconnect attempts exhausted",
                        {"returncode": rc, "attempts": max_attempts},
                    )
                    return

        self._watch_task = asyncio.create_task(watch())

    async def reset(self, force: bool = False) -> dict[str, Any]:
        async with self._lock:
            return await self._reset_unlocked(force=force)

    async def _reset_unlocked(self, force: bool = False) -> dict[str, Any]:
        running = self._supervisor.running(self.PROC_NAME)
        if running:
            if self._watch_task is not None:
                self._watch_task.cancel()
                self._watch_task = None
            self._reconnect_status.update({"state": "idle", "attempt": 0, "next_retry_in_ms": None})

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

            self._active_source = None
            self._active_proc_name = None

        result: dict[str, Any] | None = None
        try:
            result = await self._privilege_client.call(
                "v4l2.reload",
                {
                    "video_nr": self._v4l2.video_nr,
                    "label": "AVream Camera",
                    "exclusive_caps": True,
                    "force": bool(force),
                },
            )
        except ApiError as exc:
            if exc.code == "E_BUSY_DEVICE":
                blockers = self._v4l2.device_blockers()
                details = dict(exc.details or {})
                details.setdefault("device", str(self._v4l2.device_path))
                details["blocker_pids"] = blockers
                details.setdefault(
                    "hint",
                    "close applications using the camera, then retry reset; force=true may still fail while actively busy",
                )
                raise busy_device_error(
                    "cannot reset while target v4l2 device is in use",
                    details,
                )
            raise

        helper_status = None
        if isinstance(result, dict):
            helper_status = result.get("status_after") or result.get("status_before")

        return {
            "state": "RESET",
            "result": result,
            "device": str(self._v4l2.device_path),
            "helper_status": helper_status,
        }

    async def _best_effort_reload_after_stop_unlocked(self) -> dict[str, Any]:
        try:
            data = await self._privilege_client.call(
                "v4l2.reload",
                {
                    "video_nr": self._v4l2.video_nr,
                    "label": "AVream Camera",
                    "exclusive_caps": True,
                    "force": False,
                    "always_reload": True,
                },
            )
            return {"ok": True, "result": data}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def _ensure_v4l2_ready_unlocked(self) -> None:
        status = await self._privilege_client.call(
            "v4l2.status",
            {
                "video_nr": self._v4l2.video_nr,
                "label": "AVream Camera",
                "exclusive_caps": True,
            },
        )
        needs_reload = False
        if isinstance(status, dict):
            needs_reload = bool(status.get("requires_reload", False))
        if needs_reload:
            await self._privilege_client.call(
                "v4l2.reload",
                {
                    "video_nr": self._v4l2.video_nr,
                    "label": "AVream Camera",
                    "exclusive_caps": True,
                    "force": False,
                    "always_reload": False,
                },
            )
