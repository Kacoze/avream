from __future__ import annotations

import asyncio
import unittest
from typing import Any, cast

from avreamd.domain.models import ReconnectPolicy
from avreamd.managers.video.reconnect import VideoReconnectController


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------

class _ImmediateExitSupervisor:
    """Supervisor whose wait() returns immediately with a given exit code.

    On subsequent calls (after the first) it raises RuntimeError so that the
    outer ``while True`` loop in watch() exits cleanly via ``except Exception:
    return``.
    """

    def __init__(self, exit_code: int = 1) -> None:
        self._exit_code = exit_code
        self._calls = 0

    async def wait(self, name: str) -> int:
        self._calls += 1
        if self._calls > 1:
            raise RuntimeError("subsequent wait – stopping watch loop in test")
        return self._exit_code

    def running(self, name: str) -> bool:
        return False

    def last_exit_code(self, name: str) -> int:
        return self._exit_code


class _RunningStateStore:
    """State store that always reports video as RUNNING."""

    async def snapshot(self) -> dict[str, Any]:
        return {
            "started_at": "2024-01-01T00:00:00+00:00",
            "video": {"state": "RUNNING", "operation_id": 1, "last_error": None},
            "audio": {"state": "STOPPED", "operation_id": 0, "last_error": None},
        }

    async def transition_video(self, state: object) -> int:
        return 0

    async def transition_audio(self, state: object) -> int:
        return 0


class _StoppedStateStore:
    """State store that always reports video as STOPPED."""

    async def snapshot(self) -> dict[str, Any]:
        return {
            "started_at": "2024-01-01T00:00:00+00:00",
            "video": {"state": "STOPPED", "operation_id": 0, "last_error": None},
            "audio": {"state": "STOPPED", "operation_id": 0, "last_error": None},
        }

    async def transition_video(self, state: object) -> int:
        return 0

    async def transition_audio(self, state: object) -> int:
        return 0


def _make_ctrl(
    *,
    supervisor: object | None = None,
    state_store: object | None = None,
) -> VideoReconnectController:
    from avreamd.core.state_store import DaemonStateStore
    return VideoReconnectController(
        state_store=cast(Any, state_store or DaemonStateStore()),
        supervisor=cast(Any, supervisor or _ImmediateExitSupervisor()),
        proc_name="test-proc",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class VideoReconnectControllerTests(unittest.IsolatedAsyncioTestCase):

    async def test_configure_updates_policy(self) -> None:
        ctrl = _make_ctrl()
        ctrl.configure(ReconnectPolicy(enabled=True, max_attempts=5, backoff_ms=200))
        status = ctrl.runtime_status()
        self.assertEqual(status["max_attempts"], 5)
        self.assertEqual(status["backoff_ms"], 200)

    async def test_cancel_before_start_is_safe(self) -> None:
        ctrl = _make_ctrl()
        ctrl.cancel()  # Should not raise
        self.assertIsNone(ctrl._task)
        self.assertEqual(ctrl.runtime_status()["state"], "idle")

    async def test_cancel_stops_running_task(self) -> None:
        # Supervisor blocks forever after first exit so the loop doesn't end.
        class _BlockingSupervisor:
            _count = 0
            async def wait(self, name: str) -> int:
                self._count += 1
                if self._count == 1:
                    return 1
                await asyncio.Future()  # type: ignore[misc]  # never resolves
                return 0

        ctrl = _make_ctrl(
            supervisor=_BlockingSupervisor(),
            state_store=_RunningStateStore(),
        )
        ctrl.configure(ReconnectPolicy(enabled=True, max_attempts=3, backoff_ms=1))
        ctrl.start_watch(
            on_restart=lambda: asyncio.sleep(0),  # type: ignore[arg-type]
            on_exhausted=lambda rc, n: asyncio.sleep(0),  # type: ignore[arg-type]
        )
        await asyncio.sleep(0.05)
        ctrl.cancel(state="stopped")
        self.assertIsNone(ctrl._task)
        self.assertEqual(ctrl.runtime_status()["state"], "stopped")

    async def test_no_retry_when_policy_disabled(self) -> None:
        restart_calls: list[int] = []

        async def on_restart() -> None:
            restart_calls.append(1)

        async def on_exhausted(rc: int | None, n: int) -> None:
            pass

        ctrl = _make_ctrl(
            supervisor=_ImmediateExitSupervisor(exit_code=1),
            state_store=_RunningStateStore(),
        )
        ctrl.configure(ReconnectPolicy(enabled=False))
        ctrl.start_watch(on_restart=on_restart, on_exhausted=on_exhausted)
        assert ctrl._task is not None
        await asyncio.wait_for(ctrl._task, timeout=1.0)
        self.assertEqual(restart_calls, [])

    async def test_exhausts_attempts_calls_on_exhausted(self) -> None:
        exhausted_calls: list[tuple[int | None, int]] = []

        async def on_restart() -> None:
            raise RuntimeError("restart failed")

        async def on_exhausted(rc: int | None, max_attempts: int) -> None:
            exhausted_calls.append((rc, max_attempts))

        ctrl = _make_ctrl(
            supervisor=_ImmediateExitSupervisor(exit_code=42),
            state_store=_RunningStateStore(),
        )
        ctrl.configure(ReconnectPolicy(enabled=True, max_attempts=2, backoff_ms=1))
        ctrl.start_watch(on_restart=on_restart, on_exhausted=on_exhausted)
        assert ctrl._task is not None
        await asyncio.wait_for(ctrl._task, timeout=2.0)

        self.assertEqual(exhausted_calls, [(42, 2)])
        self.assertEqual(ctrl.runtime_status()["state"], "exhausted")

    async def test_recovers_on_successful_restart(self) -> None:
        async def on_restart() -> None:
            pass  # success

        async def on_exhausted(rc: int | None, max_attempts: int) -> None:
            raise AssertionError("on_exhausted should not be called")

        ctrl = _make_ctrl(
            supervisor=_ImmediateExitSupervisor(exit_code=1),
            state_store=_RunningStateStore(),
        )
        ctrl.configure(ReconnectPolicy(enabled=True, max_attempts=3, backoff_ms=1))
        ctrl.start_watch(on_restart=on_restart, on_exhausted=on_exhausted)
        assert ctrl._task is not None
        await asyncio.wait_for(ctrl._task, timeout=2.0)

        status = ctrl.runtime_status()
        self.assertEqual(status["state"], "running")
        self.assertEqual(status["attempt"], 0)

    async def test_stops_when_video_no_longer_running(self) -> None:
        restart_calls: list[int] = []

        async def on_restart() -> None:
            restart_calls.append(1)

        async def on_exhausted(rc: int | None, n: int) -> None:
            pass

        ctrl = _make_ctrl(
            supervisor=_ImmediateExitSupervisor(exit_code=0),
            state_store=_StoppedStateStore(),
        )
        ctrl.configure(ReconnectPolicy(enabled=True, max_attempts=3, backoff_ms=1))
        ctrl.start_watch(on_restart=on_restart, on_exhausted=on_exhausted)
        assert ctrl._task is not None
        await asyncio.wait_for(ctrl._task, timeout=1.0)
        self.assertEqual(restart_calls, [])


if __name__ == "__main__":
    unittest.main()
