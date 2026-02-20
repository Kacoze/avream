from __future__ import annotations

from typing import Any

from avreamd.api.errors import ApiError, busy_device_error
from avreamd.integrations.v4l2loopback import V4L2LoopbackIntegration
from avreamd.managers.privilege_client import PrivilegeClient


class VideoDeviceResetService:
    def __init__(
        self,
        *,
        privilege_client: PrivilegeClient,
        v4l2: V4L2LoopbackIntegration,
    ) -> None:
        self._privilege_client = privilege_client
        self._v4l2 = v4l2

    async def ensure_ready(self) -> None:
        status = await self._privilege_client.call(
            "v4l2.status",
            {
                "video_nr": self._v4l2.video_nr,
                "label": "AVream Camera",
                "exclusive_caps": True,
            },
        )
        if isinstance(status, dict) and bool(status.get("requires_reload", False)):
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

    async def best_effort_reload_after_stop(self) -> dict[str, Any]:
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

    async def reset(self, *, force: bool) -> dict[str, Any]:
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
                raise busy_device_error("cannot reset while target v4l2 device is in use", details)
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
