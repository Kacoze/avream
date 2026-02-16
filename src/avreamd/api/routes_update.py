from __future__ import annotations

from aiohttp import web

from avreamd.api.app_keys import UPDATE_MANAGER
from avreamd.api.errors import validation_error
from avreamd.api.schemas import success_envelope
from avreamd.api.validation import read_json_object


async def handle_update_status(request: web.Request) -> web.Response:
    request_id = request["request_id"]
    data = await request.app[UPDATE_MANAGER].runtime_status()
    return web.json_response(success_envelope(data, request_id=request_id), status=200)


async def handle_update_check(request: web.Request) -> web.Response:
    request_id = request["request_id"]
    payload = await read_json_object(request)
    force = payload.get("force", False)
    if not isinstance(force, bool):
        raise validation_error("force must be a boolean")
    data = await request.app[UPDATE_MANAGER].check(force=force)
    return web.json_response(success_envelope(data, request_id=request_id), status=200)


async def handle_update_install(request: web.Request) -> web.Response:
    request_id = request["request_id"]
    payload = await read_json_object(request)

    allow_stop_streams = payload.get("allow_stop_streams", False)
    target = payload.get("target", "latest")

    if not isinstance(allow_stop_streams, bool):
        raise validation_error("allow_stop_streams must be a boolean")
    if not isinstance(target, str):
        raise validation_error("target must be a string")

    data = await request.app[UPDATE_MANAGER].install(
        allow_stop_streams=allow_stop_streams,
        target=target,
    )
    return web.json_response(success_envelope(data, request_id=request_id), status=200)


async def handle_update_logs(request: web.Request) -> web.Response:
    request_id = request["request_id"]
    data = await request.app[UPDATE_MANAGER].logs()
    return web.json_response(success_envelope(data, request_id=request_id), status=200)


async def handle_update_config_get(request: web.Request) -> web.Response:
    request_id = request["request_id"]
    data = await request.app[UPDATE_MANAGER].get_config()
    return web.json_response(success_envelope(data, request_id=request_id), status=200)


async def handle_update_config_set(request: web.Request) -> web.Response:
    request_id = request["request_id"]
    payload = await read_json_object(request)

    auto_check = payload.get("auto_check")
    channel = payload.get("channel")
    if auto_check is not None and not isinstance(auto_check, str):
        raise validation_error("auto_check must be a string")
    if channel is not None and not isinstance(channel, str):
        raise validation_error("channel must be a string")

    data = await request.app[UPDATE_MANAGER].set_config(
        auto_check=auto_check,
        channel=channel,
    )
    return web.json_response(success_envelope(data, request_id=request_id), status=200)


def register_update_routes(app: web.Application) -> None:
    app.router.add_get("/update/status", handle_update_status)
    app.router.add_post("/update/check", handle_update_check)
    app.router.add_post("/update/install", handle_update_install)
    app.router.add_get("/update/logs", handle_update_logs)
    app.router.add_get("/update/config", handle_update_config_get)
    app.router.add_post("/update/config", handle_update_config_set)
