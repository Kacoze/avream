from __future__ import annotations

from aiohttp import web

from avreamd.api.app_keys import AUDIO_MANAGER
from avreamd.api.errors import validation_error
from avreamd.api.schemas import success_envelope
from avreamd.api.validation import read_json_object


async def handle_audio_start(request: web.Request) -> web.Response:
    request_id = request["request_id"]
    payload = await read_json_object(request)
    backend = "pipewire"
    if isinstance(payload, dict) and isinstance(payload.get("backend"), str):
        backend = payload["backend"]
    if backend not in {"pipewire", "snd_aloop"}:
        raise validation_error("backend must be one of: pipewire, snd_aloop")

    result = await request.app[AUDIO_MANAGER].start(backend=backend)
    return web.json_response(success_envelope(result, request_id=request_id), status=200)


async def handle_audio_stop(request: web.Request) -> web.Response:
    request_id = request["request_id"]
    result = await request.app[AUDIO_MANAGER].stop()
    return web.json_response(success_envelope(result, request_id=request_id), status=200)


def register_audio_routes(app: web.Application) -> None:
    app.router.add_post("/audio/start", handle_audio_start)
    app.router.add_post("/audio/stop", handle_audio_stop)
