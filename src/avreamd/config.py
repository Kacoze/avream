from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from avreamd.constants import APP_NAME, SOCKET_FILENAME, fallback_runtime_dir


@dataclass(frozen=True)
class AvreamPaths:
    runtime_dir: Path
    socket_path: Path
    config_dir: Path
    state_dir: Path
    log_dir: Path
    cache_dir: Path


def _xdg_dir(env_key: str, fallback_suffix: str) -> Path:
    env_val = os.getenv(env_key)
    if env_val:
        return Path(env_val) / APP_NAME
    return Path.home() / fallback_suffix / APP_NAME


def resolve_paths(socket_override: str | None = None) -> AvreamPaths:
    uid = os.getuid()
    runtime_root = os.getenv("XDG_RUNTIME_DIR")
    runtime_dir = Path(runtime_root) / APP_NAME if runtime_root else fallback_runtime_dir(uid)

    socket_path = Path(socket_override) if socket_override else runtime_dir / SOCKET_FILENAME
    config_dir = _xdg_dir("XDG_CONFIG_HOME", ".config")
    state_dir = _xdg_dir("XDG_STATE_HOME", ".local/state")
    cache_dir = _xdg_dir("XDG_CACHE_HOME", ".cache")
    log_dir = state_dir / "logs"

    return AvreamPaths(
        runtime_dir=runtime_dir,
        socket_path=socket_path,
        config_dir=config_dir,
        state_dir=state_dir,
        log_dir=log_dir,
        cache_dir=cache_dir,
    )


def ensure_directories(paths: AvreamPaths) -> None:
    paths.runtime_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(paths.runtime_dir, 0o700)
    paths.config_dir.mkdir(parents=True, exist_ok=True)
    paths.state_dir.mkdir(parents=True, exist_ok=True)
    paths.log_dir.mkdir(parents=True, exist_ok=True)
    paths.cache_dir.mkdir(parents=True, exist_ok=True)


def remove_stale_socket(paths: AvreamPaths) -> None:
    if paths.socket_path.exists():
        if paths.socket_path.is_socket():
            paths.socket_path.unlink()
