from __future__ import annotations

from typing import Any

from aiohttp import web


def _app_key(name: str) -> Any:
    app_key_cls = getattr(web, "AppKey", None)
    if app_key_cls is None:
        # Compatibility with aiohttp versions that do not expose web.AppKey.
        return name
    return app_key_cls(name, object)


STATE_STORE: Any = _app_key("state_store")
PATHS: Any = _app_key("paths")
VIDEO_MANAGER: Any = _app_key("video_manager")
AUDIO_MANAGER: Any = _app_key("audio_manager")
ADB_ADAPTER: Any = _app_key("adb_adapter")
PRIVILEGE_CLIENT: Any = _app_key("privilege_client")
