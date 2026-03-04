from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any, cast

from avreamd.api.errors import ApiError, busy_device_error
from avreamd.managers.video.device_reset import VideoDeviceResetService


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------

class _PrivilegeStub:
    """Configurable privilege client stub."""

    def __init__(
        self,
        *,
        requires_reload: bool = False,
        raise_busy: bool = False,
        raise_other: bool = False,
    ) -> None:
        self._requires_reload = requires_reload
        self._raise_busy = raise_busy
        self._raise_other = raise_other
        self.calls: list[str] = []

    async def call(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(action)
        if action == "v4l2.status":
            return {"requires_reload": self._requires_reload}
        if self._raise_busy:
            raise ApiError(
                code="E_BUSY_DEVICE",
                message="device is busy",
                status=409,
                details={"device": "/dev/video10"},
            )
        if self._raise_other:
            raise ApiError(
                code="E_BACKEND_FAILED",
                message="helper error",
                status=502,
            )
        return {"status_after": {"loaded": True}}


class _V4L2Stub:
    video_nr = 10
    device_path = Path("/dev/video10")

    def device_blockers(self) -> list[int]:
        return [1234]


def _make_service(priv: _PrivilegeStub) -> VideoDeviceResetService:
    return VideoDeviceResetService(
        privilege_client=cast(Any, priv),
        v4l2=cast(Any, _V4L2Stub()),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class VideoDeviceResetServiceTests(unittest.IsolatedAsyncioTestCase):

    async def test_ensure_ready_no_reload_when_not_required(self) -> None:
        priv = _PrivilegeStub(requires_reload=False)
        svc = _make_service(priv)
        await svc.ensure_ready()
        self.assertIn("v4l2.status", priv.calls)
        self.assertNotIn("v4l2.reload", priv.calls)

    async def test_ensure_ready_triggers_reload_when_required(self) -> None:
        priv = _PrivilegeStub(requires_reload=True)
        svc = _make_service(priv)
        await svc.ensure_ready()
        self.assertIn("v4l2.reload", priv.calls)

    async def test_best_effort_reload_returns_ok_true_on_success(self) -> None:
        priv = _PrivilegeStub()
        svc = _make_service(priv)
        result = await svc.best_effort_reload_after_stop()
        self.assertTrue(result["ok"])
        self.assertIn("result", result)

    async def test_best_effort_reload_returns_ok_false_on_failure(self) -> None:
        priv = _PrivilegeStub(raise_other=True)
        svc = _make_service(priv)
        result = await svc.best_effort_reload_after_stop()
        self.assertFalse(result["ok"])
        self.assertIn("error", result)
        self.assertIn("helper error", result["error"])

    async def test_reset_raises_busy_device_error(self) -> None:
        priv = _PrivilegeStub(raise_busy=True)
        svc = _make_service(priv)
        with self.assertRaises(ApiError) as ctx:
            await svc.reset(force=False)
        exc = ctx.exception
        self.assertEqual(exc.code, "E_BUSY_DEVICE")
        assert exc.details is not None
        self.assertIn("blocker_pids", exc.details)
        self.assertEqual(exc.details["blocker_pids"], [1234])

    async def test_reset_propagates_non_busy_api_error(self) -> None:
        priv = _PrivilegeStub(raise_other=True)
        svc = _make_service(priv)
        with self.assertRaises(ApiError) as ctx:
            await svc.reset(force=False)
        self.assertEqual(ctx.exception.code, "E_BACKEND_FAILED")

    async def test_reset_returns_state_dict_on_success(self) -> None:
        priv = _PrivilegeStub()
        svc = _make_service(priv)
        result = await svc.reset(force=False)
        self.assertEqual(result["state"], "RESET")
        self.assertEqual(result["device"], "/dev/video10")
        self.assertIsNotNone(result["helper_status"])

    async def test_reset_force_flag_is_passed_through(self) -> None:
        priv = _PrivilegeStub()
        svc = _make_service(priv)
        await svc.reset(force=True)
        # The reload action should have been called
        self.assertIn("v4l2.reload", priv.calls)


if __name__ == "__main__":
    unittest.main()
