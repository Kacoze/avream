from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast

from avreamd.api.errors import ApiError
from avreamd.config import AvreamPaths
from avreamd.core.state_store import DaemonStateStore
from avreamd.managers.update_manager import UpdateManager


# ---------------------------------------------------------------------------
# Shared stubs
# ---------------------------------------------------------------------------

class _VideoStub:
    async def stop(self) -> dict[str, object]:
        return {"state": "STOPPED"}


class _AudioStub:
    async def stop(self) -> dict[str, object]:
        return {"state": "STOPPED"}


class _ReleaseClientStub:
    def __init__(self, *, version: str = "9.9.9", fail: bool = False) -> None:
        self._version = version
        self._fail = fail
        self.calls: int = 0

    async def fetch_latest_release(self) -> dict[str, Any]:
        self.calls += 1
        if self._fail:
            raise RuntimeError("network error")
        return {
            "version": self._version,
            "release_url": f"https://github.com/example/releases/{self._version}",
            "recommended_asset": {
                "name": f"avream_{self._version}_amd64.deb",
                "url": f"https://example.com/avream_{self._version}_amd64.deb",
            },
            "assets": {
                "checksums": "https://example.com/SHA256SUMS.txt",
                "monolith": f"https://example.com/avream_{self._version}_amd64.deb",
            },
        }


class _DownloaderStub:
    def __init__(self, *, content: bytes = b"fake-deb") -> None:
        self._content = content

    async def download_file(self, url: str, path: Path) -> None:
        path.write_bytes(self._content)


class _VerifierStub:
    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail

    def verify_checksum(self, *, asset_name: str, deb_path: Path, sums_path: Path) -> None:
        if self._fail:
            from avreamd.api.errors import backend_error
            raise backend_error("checksum mismatch", retryable=False)


class _InstallerStub:
    async def run_install(self, deb_path: Path) -> dict[str, Any]:
        return {"returncode": 0, "stdout": "OK", "stderr": ""}


class _RestartSchedulerStub:
    def schedule_daemon_restart(self) -> None:
        pass


class _RunningVideoStateStore:
    """State store that reports video as RUNNING."""

    async def snapshot(self) -> dict[str, Any]:
        return {
            "video": {"state": "RUNNING", "operation_id": 1, "last_error": None},
            "audio": {"state": "STOPPED", "operation_id": 0, "last_error": None},
        }

    async def transition_video(self, state: object) -> int:
        return 0

    async def transition_audio(self, state: object) -> int:
        return 0


# ---------------------------------------------------------------------------
# Helper to build a manager with injected stubs
# ---------------------------------------------------------------------------

def _make_paths(root: Path) -> AvreamPaths:
    runtime = root / "runtime"
    config = root / "config"
    state = root / "state"
    log = state / "logs"
    cache = root / "cache"
    for p in (runtime, config, state, log, cache):
        p.mkdir(parents=True, exist_ok=True)
    return AvreamPaths(
        runtime_dir=runtime,
        socket_path=runtime / "daemon.sock",
        config_dir=config,
        state_dir=state,
        log_dir=log,
        cache_dir=cache,
    )


def _make_manager(
    paths: AvreamPaths,
    *,
    release_client: object | None = None,
    downloader: object | None = None,
    verifier: object | None = None,
    installer: object | None = None,
    scheduler: object | None = None,
    state_store: object | None = None,
) -> UpdateManager:
    mgr = UpdateManager(
        paths=paths,
        state_store=state_store or DaemonStateStore(),
        video_manager=_VideoStub(),
        audio_manager=_AudioStub(),
    )
    if release_client is not None:
        mgr._release_client = cast(Any, release_client)
    if downloader is not None:
        mgr._downloader = cast(Any, downloader)
    if verifier is not None:
        mgr._verifier = cast(Any, verifier)
    if installer is not None:
        mgr._installer = cast(Any, installer)
    if scheduler is not None:
        mgr._restart_scheduler = cast(Any, scheduler)
    return mgr


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class UpdateManagerTests(unittest.IsolatedAsyncioTestCase):
    # -- existing tests kept as-is --

    async def test_version_compare(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mgr = UpdateManager(
                paths=_make_paths(Path(td)),
                state_store=DaemonStateStore(),
                video_manager=_VideoStub(),
                audio_manager=_AudioStub(),
            )
            self.assertTrue(mgr._is_newer_version("1.0.1", "1.0.0"))
            self.assertFalse(mgr._is_newer_version("1.0.0", "1.0.0"))
            self.assertFalse(mgr._is_newer_version("1.0.0-beta.1", "1.0.0"))

    async def test_config_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mgr = UpdateManager(
                paths=_make_paths(Path(td)),
                state_store=DaemonStateStore(),
                video_manager=_VideoStub(),
                audio_manager=_AudioStub(),
            )
            cfg = await mgr.set_config(auto_check="weekly", channel="stable")
            self.assertEqual(cfg["auto_check"], "weekly")
            loaded = await mgr.get_config()
            self.assertEqual(loaded["auto_check"], "weekly")

    # -- new tests --

    async def test_check_sets_update_available_when_newer_version(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(
                _make_paths(Path(td)),
                release_client=_ReleaseClientStub(version="9.9.9"),
            )
            result = await mgr.check()
            self.assertTrue(result["update_available"])
            self.assertEqual(result["install_state"], "IDLE")
            self.assertEqual(result["latest_version"], "9.9.9")

    async def test_check_sets_no_update_when_same_version(self) -> None:
        from avreamd import __version__
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(
                _make_paths(Path(td)),
                release_client=_ReleaseClientStub(version=__version__),
            )
            result = await mgr.check()
            self.assertFalse(result["update_available"])
            self.assertEqual(result["install_state"], "IDLE")

    async def test_check_failure_transitions_to_failed_state(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(
                _make_paths(Path(td)),
                release_client=_ReleaseClientStub(fail=True),
            )
            with self.assertRaises(ApiError):
                await mgr.check()
            status = await mgr.runtime_status()
            self.assertEqual(status["install_state"], "FAILED")
            self.assertIsNotNone(status["last_error"])

    async def test_install_already_up_to_date(self) -> None:
        from avreamd import __version__
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(
                _make_paths(Path(td)),
                release_client=_ReleaseClientStub(version=__version__),
            )
            result = await mgr.install()
            self.assertTrue(result["already_up_to_date"])
            self.assertEqual(result["state"], "DONE")
            status = await mgr.runtime_status()
            self.assertEqual(status["install_state"], "DONE")
            self.assertEqual(status["progress"], 100)

    async def test_install_full_flow_happy_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(
                _make_paths(Path(td)),
                release_client=_ReleaseClientStub(version="9.9.9"),
                downloader=_DownloaderStub(),
                verifier=_VerifierStub(),
                installer=_InstallerStub(),
                scheduler=_RestartSchedulerStub(),
            )
            result = await mgr.install()
            self.assertFalse(result["already_up_to_date"])
            self.assertEqual(result["state"], "DONE")
            self.assertTrue(result.get("restart_scheduled"))
            status = await mgr.runtime_status()
            self.assertEqual(status["install_state"], "DONE")
            self.assertEqual(status["progress"], 100)

    async def test_install_blocked_by_running_streams(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(
                _make_paths(Path(td)),
                release_client=_ReleaseClientStub(version="9.9.9"),
                state_store=cast(Any, _RunningVideoStateStore()),
            )
            with self.assertRaises(ApiError) as ctx:
                await mgr.install(allow_stop_streams=False)
            self.assertEqual(ctx.exception.code, "E_CONFLICT")
            status = await mgr.runtime_status()
            self.assertEqual(status["install_state"], "FAILED")

    async def test_install_stops_streams_when_allowed(self) -> None:
        from avreamd import __version__
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(
                _make_paths(Path(td)),
                release_client=_ReleaseClientStub(version=__version__),
                state_store=cast(Any, _RunningVideoStateStore()),
            )
            result = await mgr.install(allow_stop_streams=True)
            self.assertTrue(result["already_up_to_date"])

    async def test_install_checksum_failure_propagates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(
                _make_paths(Path(td)),
                release_client=_ReleaseClientStub(version="9.9.9"),
                downloader=_DownloaderStub(),
                verifier=_VerifierStub(fail=True),
            )
            with self.assertRaises(ApiError):
                await mgr.install()

    async def test_start_background_creates_task_and_stop_cancels(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mgr = _make_manager(_make_paths(Path(td)))
            await mgr.start_background()
            self.assertIsNotNone(mgr._auto_task)
            # Second call is a no-op
            await mgr.start_background()
            self.assertIsNotNone(mgr._auto_task)
            await mgr.stop_background()
            self.assertIsNone(mgr._auto_task)

    async def test_auto_loop_does_not_check_when_auto_off(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            rc = _ReleaseClientStub(version="9.9.9")
            mgr = _make_manager(_make_paths(Path(td)), release_client=rc)
            await mgr.set_config(auto_check="off")
            await mgr.start_background()
            await asyncio.sleep(0.05)
            await mgr.stop_background()
            self.assertEqual(rc.calls, 0)


if __name__ == "__main__":
    unittest.main()
