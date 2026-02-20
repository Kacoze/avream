from __future__ import annotations

from dataclasses import dataclass

from avreamd.backends.android_video import AndroidVideoBackend
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


@dataclass
class DaemonDeps:
    state_store: DaemonStateStore
    supervisor: ProcessSupervisor
    privilege_client: PrivilegeClient
    pipewire: PipeWireIntegration
    pactl: PactlIntegration
    v4l2: V4L2LoopbackIntegration
    adb: AdbAdapter
    audio_manager: AudioManager
    android_backend: AndroidVideoBackend
    video_manager: VideoManager
    update_manager: UpdateManager


def build_daemon_deps(paths) -> DaemonDeps:
    state_store = DaemonStateStore()
    supervisor = ProcessSupervisor(log_dir=paths.log_dir)
    privilege_client = PrivilegeClient()
    pipewire = PipeWireIntegration()
    pactl = PactlIntegration()
    v4l2 = V4L2LoopbackIntegration(video_nr=10)
    adb = AdbAdapter()
    audio_manager = AudioManager(
        state_store=state_store,
        pipewire=pipewire,
        pactl=pactl,
        privilege_client=privilege_client,
        state_dir=paths.state_dir,
    )
    android_backend = AndroidVideoBackend(adb=adb, scrcpy=ScrcpyAdapter())
    video_manager = VideoManager(
        state_store=state_store,
        backend=android_backend,
        supervisor=supervisor,
        privilege_client=privilege_client,
        v4l2=v4l2,
        audio_manager=audio_manager,
    )
    update_manager = UpdateManager(
        paths=paths,
        state_store=state_store,
        video_manager=video_manager,
        audio_manager=audio_manager,
    )
    return DaemonDeps(
        state_store=state_store,
        supervisor=supervisor,
        privilege_client=privilege_client,
        pipewire=pipewire,
        pactl=pactl,
        v4l2=v4l2,
        adb=adb,
        audio_manager=audio_manager,
        android_backend=android_backend,
        video_manager=video_manager,
        update_manager=update_manager,
    )
