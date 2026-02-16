from __future__ import annotations

from aiohttp import web

from avreamd.api.app_keys import (
    ADB_ADAPTER,
    AUDIO_MANAGER,
    PATHS,
    PRIVILEGE_CLIENT,
    STATE_STORE,
    VIDEO_MANAGER,
)
from avreamd.api.middleware import request_context_middleware
from avreamd.api.routes_audio import register_audio_routes
from avreamd.api.routes_android import register_android_routes
from avreamd.api.routes_status import register_status_routes
from avreamd.api.routes_video import register_video_routes


def create_api_app(
    *,
    state_store,
    paths,
    video_manager,
    audio_manager,
    adb_adapter,
    privilege_client,
) -> web.Application:
    app = web.Application(middlewares=[request_context_middleware])
    app[STATE_STORE] = state_store
    app[PATHS] = paths
    app[VIDEO_MANAGER] = video_manager
    app[AUDIO_MANAGER] = audio_manager
    app[ADB_ADAPTER] = adb_adapter
    app[PRIVILEGE_CLIENT] = privilege_client

    register_status_routes(app)
    register_video_routes(app)
    register_audio_routes(app)
    register_android_routes(app)
    return app
