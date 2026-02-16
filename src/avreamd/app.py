from __future__ import annotations

import asyncio
import logging

from aiohttp import web

from avreamd.api.server import create_api_app
from avreamd.backends.android_video import AndroidVideoBackend
from avreamd.config import ensure_directories, remove_stale_socket
from avreamd.core.process_supervisor import ProcessSupervisor
from avreamd.core.state_store import DaemonStateStore
from avreamd.integrations.adb import AdbAdapter
from avreamd.integrations.pactl import PactlIntegration
from avreamd.integrations.pipewire import PipeWireIntegration
from avreamd.integrations.scrcpy import ScrcpyAdapter
from avreamd.integrations.v4l2loopback import V4L2LoopbackIntegration
from avreamd.managers.audio_manager import AudioManager
from avreamd.managers.privilege_client import PrivilegeClient
from avreamd.managers.update_manager import UpdateManager
from avreamd.managers.video_manager import VideoManager


logger = logging.getLogger(__name__)


class AvreamDaemon:
    def __init__(self, paths) -> None:
        self.paths = paths
        self.state_store = DaemonStateStore()
        self.supervisor = ProcessSupervisor(log_dir=paths.log_dir)
        self.privilege_client = PrivilegeClient()
        self.pipewire = PipeWireIntegration()
        self.pactl = PactlIntegration()
        self.v4l2 = V4L2LoopbackIntegration(video_nr=10)
        self.adb = AdbAdapter()
        self.audio_manager = AudioManager(
            state_store=self.state_store,
            pipewire=self.pipewire,
            pactl=self.pactl,
            privilege_client=self.privilege_client,
            state_dir=paths.state_dir,
        )
        self.android_backend = AndroidVideoBackend(adb=self.adb, scrcpy=ScrcpyAdapter())
        self.video_manager = VideoManager(
            state_store=self.state_store,
            backend=self.android_backend,
            supervisor=self.supervisor,
            privilege_client=self.privilege_client,
            v4l2=self.v4l2,
            audio_manager=self.audio_manager,
        )
        self.update_manager = UpdateManager(
            paths=paths,
            state_store=self.state_store,
            video_manager=self.video_manager,
            audio_manager=self.audio_manager,
        )
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
