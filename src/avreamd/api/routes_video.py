from __future__ import annotations

from aiohttp import web

from avreamd.api.errors import validation_error
from avreamd.api.app_keys import VIDEO_MANAGER
from avreamd.api.schemas import success_envelope
from avreamd.api.validation import get_bool, read_json_object


async def handle_video_start(request: web.Request) -> web.Response:
    request_id = request["request_id"]
    payload = await read_json_object(request)
    serial = payload.get("serial") if isinstance(payload, dict) else None
    camera_facing = payload.get("camera_facing") if isinstance(payload, dict) else None
    camera_rotation = payload.get("camera_rotation") if isinstance(payload, dict) else None
    preview_window = payload.get("preview_window") if isinstance(payload, dict) else None
    if camera_facing is not None:
        if not isinstance(camera_facing, str) or camera_facing not in {"front", "back"}:
            raise validation_error("camera_facing must be 'front' or 'back'")
    if preview_window is not None and not isinstance(preview_window, bool):
        raise validation_error("preview_window must be boolean")
    if camera_rotation is not None:
        if isinstance(camera_rotation, bool) or not isinstance(camera_rotation, int):
            raise validation_error("camera_rotation must be one of: 0, 90, 180, 270")
        if camera_rotation not in {0, 90, 180, 270}:
            raise validation_error("camera_rotation must be one of: 0, 90, 180, 270")
    result = await request.app[VIDEO_MANAGER].start(
        serial=serial,
        camera_facing=camera_facing,
        camera_rotation=camera_rotation,
        preview_window=preview_window,
    )
    return web.json_response(success_envelope(result, request_id=request_id), status=200)


async def handle_video_stop(request: web.Request) -> web.Response:
    request_id = request["request_id"]
    result = await request.app[VIDEO_MANAGER].stop()
    return web.json_response(success_envelope(result, request_id=request_id), status=200)


async def handle_video_reset(request: web.Request) -> web.Response:
    request_id = request["request_id"]
    payload = await read_json_object(request)
    force = get_bool(payload, "force", default=False)
    result = await request.app[VIDEO_MANAGER].reset(force=force)
    return web.json_response(success_envelope(result, request_id=request_id), status=200)


def register_video_routes(app: web.Application) -> None:
    app.router.add_post("/video/start", handle_video_start)
    app.router.add_post("/video/stop", handle_video_stop)
    app.router.add_post("/video/reset", handle_video_reset)
