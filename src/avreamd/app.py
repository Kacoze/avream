from __future__ import annotations

import asyncio
import logging

from aiohttp import web

from avreamd.api.server import create_api_app
from avreamd.bootstrap import build_daemon_deps
from avreamd.config import ensure_directories, remove_stale_socket


logger = logging.getLogger(__name__)


class AvreamDaemon:
    def __init__(self, paths) -> None:
        self.paths = paths
        deps = build_daemon_deps(paths)
        self.state_store = deps.state_store
        self.supervisor = deps.supervisor
        self.privilege_client = deps.privilege_client
        self.pipewire = deps.pipewire
        self.pactl = deps.pactl
        self.v4l2 = deps.v4l2
        self.adb = deps.adb
        self.audio_manager = deps.audio_manager
        self.android_backend = deps.android_backend
        self.video_manager = deps.video_manager
        self.update_manager = deps.update_manager
        self._runner: web.AppRunner | None = None
        self._site: web.UnixSite | None = None
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        ensure_directories(self.paths)
        remove_stale_socket(self.paths)

        app = create_api_app(
            state_store=self.state_store,
            paths=self.paths,
            video_manager=self.video_manager,
            audio_manager=self.audio_manager,
            update_manager=self.update_manager,
            adb_adapter=self.adb,
            privilege_client=self.privilege_client,
        )
        self._runner = web.AppRunner(app, access_log=None)
        assert self._runner is not None
        await self._runner.setup()
        self._site = web.UnixSite(self._runner, path=str(self.paths.socket_path))
        assert self._site is not None
        await self._site.start()
        await self.update_manager.start_background()
        logger.info("avreamd listening on unix socket: %s", self.paths.socket_path)

    async def stop(self) -> None:
        self._shutdown_event.set()
        await self.update_manager.stop_background()
        await self.supervisor.stop_all()
        if self._runner is not None:
            await self._runner.cleanup()
        remove_stale_socket(self.paths)
        logger.info("avreamd stopped")

    async def wait_until_shutdown(self) -> None:
        await self._shutdown_event.wait()

    def request_shutdown(self) -> None:
        self._shutdown_event.set()
