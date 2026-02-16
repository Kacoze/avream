from __future__ import annotations

from aiohttp import web

from avreamd.api.app_keys import PATHS, PRIVILEGE_CLIENT, STATE_STORE, VIDEO_MANAGER
from avreamd.api.schemas import success_envelope
from avreamd.constants import API_VERSION, APP_NAME, DAEMON_NAME


async def handle_status(request: web.Request) -> web.Response:
    state_store = request.app[STATE_STORE]
    paths = request.app[PATHS]
    video_manager = request.app[VIDEO_MANAGER]
    privilege_client = request.app[PRIVILEGE_CLIENT]
    request_id = request["request_id"]

    runtime = await state_store.snapshot()
    video_runtime = await video_manager.runtime_status()
    data = {
        "service": {
            "app": APP_NAME,
            "daemon": DAEMON_NAME,
            "api_version": API_VERSION,
            "socket_path": str(paths.socket_path),
            "helper": privilege_client.diagnostics(),
        },
        "video_runtime": video_runtime,
        "runtime": runtime,
    }
    return web.json_response(success_envelope(data, request_id=request_id), status=200)


def register_status_routes(app: web.Application) -> None:
    app.router.add_get("/status", handle_status)
