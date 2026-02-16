from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aiohttp import ClientSession, ClientTimeout

from avreamd import __version__
from avreamd.api.errors import backend_error, conflict_error, dependency_error, validation_error


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
            release = await self._fetch_latest_release()
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
        await self._download_file(asset_url, deb_path)
        await self._download_file(checksum_url, sums_path)

        async with self._lock:
            self._runtime["install_state"] = "VERIFYING"
            self._runtime["progress"] = 55
            self._save_state()

        self._verify_checksum(asset_name=asset_name, deb_path=deb_path, sums_path=sums_path)

        async with self._lock:
            self._runtime["install_state"] = "INSTALLING"
            self._runtime["progress"] = 75
            self._save_state()

        install_result = await self._run_install(deb_path)

        async with self._lock:
            self._runtime["install_state"] = "DONE"
            self._runtime["progress"] = 100
            self._runtime["last_error"] = None
            self._save_state()
            self._append_log("update.install.done", {"result": install_result})

        self._schedule_daemon_restart()
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

    async def _fetch_latest_release(self) -> dict[str, Any]:
        url = f"{self._api_base}/repos/{self._repo}/releases/latest"
        timeout = ClientTimeout(total=20, connect=10, sock_read=20)
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "avream-updater",
        }
        async with ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    raise backend_error("release API returned error", {"status": resp.status, "body": text[:1000]})
                payload = await resp.json(content_type=None)

        if not isinstance(payload, dict):
            raise backend_error("invalid release metadata response")

        tag_name = str(payload.get("tag_name", "")).strip()
        version = tag_name[1:] if tag_name.startswith("v") else tag_name
        if not version:
            raise backend_error("release tag is missing")

        assets = payload.get("assets")
        if not isinstance(assets, list):
            assets = []

        by_name: dict[str, dict[str, str]] = {}
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            name = asset.get("name")
            dl = asset.get("browser_download_url")
            if isinstance(name, str) and isinstance(dl, str):
                by_name[name] = {"name": name, "url": dl}

        monolith = by_name.get(f"avream_{version}_amd64.deb")
        if not monolith:
            raise backend_error("monolithic .deb asset not found", {"version": version})

        checksums = by_name.get("SHA256SUMS.txt")
        if not checksums:
            raise backend_error("SHA256SUMS.txt asset not found", {"version": version})

        release_url = payload.get("html_url")
        if not isinstance(release_url, str) or not release_url:
            release_url = f"https://github.com/{self._repo}/releases/latest"

        return {
            "version": version,
            "release_url": release_url,
            "recommended_asset": monolith,
            "assets": {
                "checksums": checksums["url"],
                "monolith": monolith["url"],
                "split_archive": by_name.get(f"avream-deb-split_{version}_amd64.tar.gz", {}).get("url", ""),
            },
        }

    async def _download_file(self, url: str, path: Path) -> None:
        timeout = ClientTimeout(total=120, connect=20, sock_read=120)
        headers = {"Accept": "application/octet-stream", "User-Agent": "avream-updater"}
        async with ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    raise backend_error("download failed", {"url": url, "status": resp.status, "body": text[:1000]})
                with path.open("wb") as handle:
                    async for chunk in resp.content.iter_chunked(1024 * 64):
                        handle.write(chunk)

    def _verify_checksum(self, *, asset_name: str, deb_path: Path, sums_path: Path) -> None:
        sums_text = sums_path.read_text(encoding="utf-8", errors="replace")
        expected = None
        for line in sums_text.splitlines():
            parts = line.strip().split()
            if len(parts) >= 2 and parts[-1].endswith(asset_name):
                expected = parts[0]
                break
        if not expected:
            raise backend_error("checksum entry for asset not found", {"asset": asset_name})

        digest = hashlib.sha256(deb_path.read_bytes()).hexdigest()
        if digest.lower() != expected.lower():
            raise backend_error(
                "checksum mismatch",
                {"asset": asset_name, "expected": expected, "actual": digest},
                retryable=False,
            )

    async def _run_install(self, deb_path: Path) -> dict[str, Any]:
        pkexec = shutil.which("pkexec")
        if not pkexec:
            raise dependency_error("pkexec is missing", {"tool": "pkexec", "package": "policykit-1"})

        if self._install_tool not in {"apt", "apt-get"}:
            raise validation_error("unsupported install tool", {"install_tool": self._install_tool})

        install_bin = shutil.which(self._install_tool)
        if not install_bin:
            raise dependency_error(f"{self._install_tool} is missing", {"tool": self._install_tool})

        cmd = [pkexec, install_bin, "install", "-y", str(deb_path)]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_b, stderr_b = await proc.communicate()
        stdout = stdout_b.decode("utf-8", errors="replace")
        stderr = stderr_b.decode("utf-8", errors="replace")
        rc = int(proc.returncode or 0)
        if rc != 0:
            raise backend_error(
                "update installation failed",
                {
                    "returncode": rc,
                    "stdout": stdout[-3000:],
                    "stderr": stderr[-3000:],
                },
                retryable=False,
            )
        return {"returncode": rc, "stdout": stdout[-1000:], "stderr": stderr[-1000:]}

    def _schedule_daemon_restart(self) -> None:
        cmd = [
            "bash",
            "-lc",
            "(sleep 1; systemctl --user restart avreamd.service) >/dev/null 2>&1 &",
        ]
        try:
            subprocess.Popen(cmd)
        except Exception:
            logger.exception("failed to schedule avreamd restart after update")

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _version_key(version: str) -> tuple[int, int, int, int, str]:
        # (major, minor, patch, prerelease_flag, prerelease_text)
        # prerelease_flag: 1 = final, 0 = prerelease
        text = version.strip().lstrip("v")
        m = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:[-~]?([0-9A-Za-z.-]+))?$", text)
        if not m:
            return (0, 0, 0, 0, text)
        major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))
        pre = m.group(4) or ""
        return (major, minor, patch, 0 if pre else 1, pre)

    def _is_newer_version(self, latest: str, current: str) -> bool:
        return self._version_key(latest) > self._version_key(current)
