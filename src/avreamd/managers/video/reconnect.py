from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable

from avreamd.core.process_supervisor import ProcessSupervisor
from avreamd.core.state_store import DaemonStateStore, SubsystemState
from avreamd.domain.models import ReconnectPolicy, ReconnectStatus


class VideoReconnectController:
    def __init__(self, *, state_store: DaemonStateStore, supervisor: ProcessSupervisor, proc_name: str) -> None:
        self._state_store = state_store
        self._supervisor = supervisor
        self._proc_name = proc_name
        self._task: asyncio.Task | None = None
        self._policy = ReconnectPolicy().normalized()
        self._status = ReconnectStatus.from_policy(self._policy)

    def configure(self, policy: ReconnectPolicy) -> None:
        self._policy = policy.normalized()
        self._status = ReconnectStatus.from_policy(self._policy)

    def runtime_status(self) -> dict[str, object]:
        return self._status.as_dict()

    def cancel(self, state: str = "idle") -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None
        self._status.state = state
        self._status.attempt = 0
        self._status.next_retry_in_ms = None

    def start_watch(
        self,
        *,
        on_restart: Callable[[], Awaitable[None]],
        on_exhausted: Callable[[int | None, int], Awaitable[None]],
    ) -> None:
        if self._task is not None:
            self._task.cancel()

        async def watch() -> None:
            while True:
                try:
                    rc = await self._supervisor.wait(self._proc_name)
                except Exception:
                    return

                if not self._policy.enabled:
                    return

                self._status.enabled = True
                self._status.max_attempts = self._policy.max_attempts
                self._status.backoff_ms = self._policy.backoff_ms
                self._status.last_exit_code = rc
                self._status.state = "exited"
                self._status.attempt = 0
                self._status.next_retry_in_ms = None

                snap = await self._state_store.snapshot()
                if snap["video"]["state"] != SubsystemState.RUNNING.value:
                    return

                for attempt in range(1, self._policy.max_attempts + 1):
                    self._status.attempt = attempt
                    self._status.state = "waiting"
                    self._status.next_retry_in_ms = int(self._policy.backoff_ms)
                    next_at = time.monotonic() + (self._policy.backoff_ms / 1000.0)
                    await asyncio.sleep(self._policy.backoff_ms / 1000.0)
                    if time.monotonic() >= next_at:
                        self._status.next_retry_in_ms = 0

                    snap = await self._state_store.snapshot()
                    if snap["video"]["state"] != SubsystemState.RUNNING.value:
                        return

                    self._status.state = "restarting"
                    try:
                        await self._state_store.transition_video(SubsystemState.STARTING)
                    except Exception:
                        pass

                    try:
                        await on_restart()
                        self._status.state = "running"
                        self._status.attempt = 0
                        self._status.next_retry_in_ms = None
                        break
                    except Exception:
                        try:
                            await self._state_store.transition_video(SubsystemState.RUNNING)
                        except Exception:
                            pass
                        self._status.state = "failed"
                else:
                    self._status.state = "exhausted"
                    self._status.next_retry_in_ms = None
                    await on_exhausted(rc, self._policy.max_attempts)
                    return

        self._task = asyncio.create_task(watch())
