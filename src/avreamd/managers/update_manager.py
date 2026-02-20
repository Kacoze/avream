from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from avreamd import __version__
from avreamd.api.errors import backend_error, conflict_error, validation_error
from avreamd.managers.update import AssetDownloader, ChecksumVerifier, PackageInstaller, ReleaseClient, RestartScheduler


logger = logging.getLogger(__name__)


class UpdateManager:
    def __init__(
        self,
        *,
        paths,
        state_store,
        video_manager,
        audio_manager,
    ) -> None:
        self._paths = paths
        self._state_store = state_store
        self._video_manager = video_manager
        self._audio_manager = audio_manager
        self._lock = asyncio.Lock()
        self._logs: deque[dict[str, Any]] = deque(maxlen=300)
        self._stop_event = asyncio.Event()
        self._auto_task: asyncio.Task | None = None

        self._repo = os.getenv("AVREAM_UPDATE_REPO", "Kacoze/avream")
        self._api_base = os.getenv("AVREAM_UPDATE_API_BASE", "https://api.github.com")
        self._install_tool = os.getenv("AVREAM_UPDATE_INSTALL_TOOL", "apt")

        self._release_client = ReleaseClient(api_base=self._api_base, repo=self._repo)
        self._downloader = AssetDownloader()
        self._verifier = ChecksumVerifier()
        self._installer = PackageInstaller(install_tool=self._install_tool)
        self._restart_scheduler = RestartScheduler()

        self._cfg_path = self._paths.config_dir / "update.json"
        self._state_path = self._paths.state_dir / "update-state.json"
        self._cache_dir = self._paths.cache_dir / "updates"
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        self._config: dict[str, Any] = {
            "auto_check": "daily",
            "channel": "stable",
        }
        self._runtime: dict[str, Any] = {
            "current_version": __version__,
            "latest_version": __version__,
            "update_available": False,
            "channel": "stable",
            "last_checked_at": None,
            "last_error": None,
            "install_state": "IDLE",
            "latest_release_url": f"https://github.com/{self._repo}/releases/latest",
            "recommended_asset": None,
            "assets": {},
            "progress": 0,
        }
        self._load_config()
        self._load_state()

    async def start_background(self) -> None:
        if self._auto_task is not None:
            return
        self._stop_event.clear()
        self._auto_task = asyncio.create_task(self._auto_loop())

    async def stop_background(self) -> None:
        self._stop_event.set()
        if self._auto_task is not None:
            self._auto_task.cancel()
            try:
                await self._auto_task
            except BaseException:
                pass
            self._auto_task = None

    async def runtime_status(self) -> dict[str, Any]:
        async with self._lock:
            out = dict(self._runtime)
            out["config"] = dict(self._config)
            return out

    async def logs(self) -> dict[str, Any]:
        async with self._lock:
            return {"events": list(self._logs)}

    async def get_config(self) -> dict[str, Any]:
        async with self._lock:
            return dict(self._config)

    async def set_config(self, *, auto_check: str | None = None, channel: str | None = None) -> dict[str, Any]:
        async with self._lock:
            if auto_check is not None:
                if auto_check not in {"off", "daily", "weekly"}:
                    raise validation_error("auto_check must be one of: off,daily,weekly")
                self._config["auto_check"] = auto_check
            if channel is not None:
                if channel not in {"stable"}:
                    raise validation_error("only stable channel is currently supported")
                self._config["channel"] = channel
                self._runtime["channel"] = channel
            self._save_config()
            self._append_log("config.updated", {"config": dict(self._config)})
            return dict(self._config)

    async def check(self, *, force: bool = False) -> dict[str, Any]:
        async with self._lock:
            if self._runtime["install_state"] in {"DOWNLOADING", "VERIFYING", "INSTALLING"}:
                raise conflict_error("update install is in progress")
            self._runtime["install_state"] = "CHECKING"
            self._runtime["progress"] = 0
            self._runtime["last_error"] = None
            self._append_log("update.check.start", {"force": bool(force)})

        try:
            release = await self._release_client.fetch_latest_release()
            latest_version = str(release["version"])
            current_version = str(__version__)
            update_available = self._is_newer_version(latest_version, current_version)

            async with self._lock:
                self._runtime.update(
                    {
                        "current_version": current_version,
                        "latest_version": latest_version,
                        "update_available": update_available,
                        "last_checked_at": self._now_iso(),
                        "latest_release_url": release["release_url"],
                        "recommended_asset": release["recommended_asset"],
                        "assets": release["assets"],
                        "install_state": "IDLE",
                        "progress": 100,
                        "last_error": None,
                    }
                )
                self._save_state()
                self._append_log(
                    "update.check.done",
                    {
                        "current_version": current_version,
                        "latest_version": latest_version,
                        "update_available": update_available,
                    },
                )
                return dict(self._runtime)
        except Exception as exc:
            message = str(exc)
            async with self._lock:
                self._runtime["install_state"] = "FAILED"
                self._runtime["progress"] = 0
                self._runtime["last_error"] = {
                    "code": "E_UPDATE_CHECK_FAILED",
                    "message": message,
                    "ts": self._now_iso(),
                }
                self._save_state()
                self._append_log("update.check.failed", {"error": message})
            if isinstance(exc, Exception) and hasattr(exc, "code"):
                raise
            raise backend_error("failed to check for updates", {"error": message}, retryable=True) from exc

    async def install(self, *, allow_stop_streams: bool = False, target: str = "latest") -> dict[str, Any]:
        if target != "latest":
            raise validation_error("only target=latest is currently supported")

        async with self._lock:
            if self._runtime["install_state"] in {"DOWNLOADING", "VERIFYING", "INSTALLING"}:
                raise conflict_error("update install is already in progress")
            self._runtime["install_state"] = "CHECKING"
            self._runtime["progress"] = 0
            self._runtime["last_error"] = None
            self._save_state()
            self._append_log("update.install.start", {"allow_stop_streams": bool(allow_stop_streams)})

        runtime = await self._state_store.snapshot()
        video_state = str(runtime.get("video", {}).get("state", ""))
        audio_state = str(runtime.get("audio", {}).get("state", ""))
        active_streams = video_state == "RUNNING" or audio_state == "RUNNING"

        if active_streams and not allow_stop_streams:
            async with self._lock:
                self._runtime["install_state"] = "FAILED"
                self._runtime["last_error"] = {
                    "code": "E_CONFLICT",
                    "message": "camera or microphone is running",
                    "ts": self._now_iso(),
                }
                self._save_state()
            raise conflict_error("camera or microphone is running", {"video": video_state, "audio": audio_state})

        if active_streams and allow_stop_streams:
            self._append_log("update.install.stop_streams", {"video": video_state, "audio": audio_state})
            if video_state == "RUNNING":
                await self._video_manager.stop()
            elif audio_state == "RUNNING":
                await self._audio_manager.stop()

        status = await self.check(force=True)
        if not bool(status.get("update_available", False)):
            async with self._lock:
                self._runtime["install_state"] = "DONE"
                self._runtime["progress"] = 100
                self._save_state()
            return {
                "state": "DONE",
                "already_up_to_date": True,
                "current_version": status.get("current_version"),
                "latest_version": status.get("latest_version"),
            }

        asset = status.get("recommended_asset") if isinstance(status, dict) else None
        if not isinstance(asset, dict):
            raise backend_error("recommended update asset is missing")

        asset_url = str(asset.get("url") or "")
        asset_name = str(asset.get("name") or "")
        checksum_url = str(status.get("assets", {}).get("checksums", ""))
        if not asset_url or not asset_name or not checksum_url:
            raise backend_error("release metadata is incomplete", {"asset": asset_name})

        async with self._lock:
            self._runtime["install_state"] = "DOWNLOADING"
            self._runtime["progress"] = 20
            self._save_state()

        deb_path = self._cache_dir / asset_name
        sums_path = self._cache_dir / "SHA256SUMS.txt"
        await self._downloader.download_file(asset_url, deb_path)
        await self._downloader.download_file(checksum_url, sums_path)

        async with self._lock:
            self._runtime["install_state"] = "VERIFYING"
            self._runtime["progress"] = 55
            self._save_state()

        self._verifier.verify_checksum(asset_name=asset_name, deb_path=deb_path, sums_path=sums_path)

        async with self._lock:
            self._runtime["install_state"] = "INSTALLING"
            self._runtime["progress"] = 75
            self._save_state()

        install_result = await self._installer.run_install(deb_path)

        async with self._lock:
            self._runtime["install_state"] = "DONE"
            self._runtime["progress"] = 100
            self._runtime["last_error"] = None
            self._save_state()
            self._append_log("update.install.done", {"result": install_result})

        try:
            self._restart_scheduler.schedule_daemon_restart()
        except Exception:
            logger.exception("failed to schedule avreamd restart after update")

        return {
            "state": "DONE",
            "already_up_to_date": False,
            "installed_asset": asset_name,
            "target_version": status.get("latest_version"),
            "restart_scheduled": True,
            "install_result": install_result,
        }

    def _load_config(self) -> None:
        try:
            if self._cfg_path.exists():
                data = json.loads(self._cfg_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    auto_check = str(data.get("auto_check", "daily"))
                    channel = str(data.get("channel", "stable"))
                    if auto_check in {"off", "daily", "weekly"}:
                        self._config["auto_check"] = auto_check
                    if channel in {"stable"}:
                        self._config["channel"] = channel
        except Exception:
            logger.exception("failed to load update config")

    def _save_config(self) -> None:
        self._cfg_path.parent.mkdir(parents=True, exist_ok=True)
        self._cfg_path.write_text(json.dumps(self._config, indent=2) + "\n", encoding="utf-8")

    def _load_state(self) -> None:
        try:
            if self._state_path.exists():
                data = json.loads(self._state_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._runtime.update({k: v for k, v in data.items() if k in self._runtime})
        except Exception:
            logger.exception("failed to load update state")

    def _save_state(self) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(json.dumps(self._runtime, indent=2) + "\n", encoding="utf-8")

    def _append_log(self, event: str, data: dict[str, Any] | None = None) -> None:
        self._logs.append({"ts": self._now_iso(), "event": event, "data": data or {}})

    async def _auto_loop(self) -> None:
        while not self._stop_event.is_set():
            interval = self._auto_interval_seconds()
            if interval is None:
                await asyncio.sleep(60)
                continue
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval)
                continue
            except TimeoutError:
                pass
            try:
                await self.check(force=False)
            except Exception as exc:
                self._append_log("update.auto_check.failed", {"error": str(exc)})

    def _auto_interval_seconds(self) -> int | None:
        mode = str(self._config.get("auto_check", "daily"))
        if mode == "off":
            return None
        if mode == "weekly":
            return 7 * 24 * 3600
        return 24 * 3600

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _version_key(version: str) -> tuple[int, int, int, int, str]:
        text = version.strip().lstrip("v")
        m = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:[-~]?([0-9A-Za-z.-]+))?$", text)
        if not m:
            return (0, 0, 0, 0, text)
        major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))
        pre = m.group(4) or ""
        return (major, minor, patch, 0 if pre else 1, pre)

    def _is_newer_version(self, latest: str, current: str) -> bool:
        return self._version_key(latest) > self._version_key(current)
