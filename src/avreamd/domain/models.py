from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class VideoStartOptions:
    serial: str | None = None
    camera_facing: str = "front"
    camera_rotation: int = 0
    preview_window: bool = False
    enable_audio: bool = True
    preset: str = "balanced"


@dataclass(frozen=True)
class VideoSource:
    serial: str
    camera_facing: str
    camera_rotation: int
    preview_window: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "type": "android",
            "serial": self.serial,
            "camera_facing": self.camera_facing,
            "camera_rotation": self.camera_rotation,
            "preview_window": self.preview_window,
        }


@dataclass(frozen=True)
class ReconnectPolicy:
    enabled: bool = True
    max_attempts: int = 3
    backoff_ms: int = 1500

    def normalized(self) -> "ReconnectPolicy":
        if not self.enabled:
            return ReconnectPolicy(enabled=False, max_attempts=0, backoff_ms=0)
        return ReconnectPolicy(
            enabled=True,
            max_attempts=max(0, min(int(self.max_attempts), 20)),
            backoff_ms=max(100, min(int(self.backoff_ms), 60000)),
        )


@dataclass
class ReconnectStatus:
    enabled: bool = True
    state: str = "idle"
    attempt: int = 0
    max_attempts: int = 3
    backoff_ms: int = 1500
    next_retry_in_ms: int | None = None
    last_exit_code: int | None = None

    @classmethod
    def from_policy(cls, policy: ReconnectPolicy) -> "ReconnectStatus":
        p = policy.normalized()
        return cls(
            enabled=p.enabled,
            state="idle",
            attempt=0,
            max_attempts=p.max_attempts,
            backoff_ms=p.backoff_ms,
            next_retry_in_ms=None,
            last_exit_code=None,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "state": self.state,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "backoff_ms": self.backoff_ms,
            "next_retry_in_ms": self.next_retry_in_ms,
            "last_exit_code": self.last_exit_code,
        }


@dataclass(frozen=True)
class UpdateConfig:
    auto_check: str = "daily"
    channel: str = "stable"

    def as_dict(self) -> dict[str, str]:
        return {"auto_check": self.auto_check, "channel": self.channel}


@dataclass(frozen=True)
class UpdateRuntime:
    current_version: str
    latest_version: str
    update_available: bool
    channel: str
    last_checked_at: str | None
    install_state: str
    progress: int


@dataclass(frozen=True)
class AdbCommandResult:
    returncode: int
    stdout: str
    stderr: str
    args: list[str]

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "AdbCommandResult":
        return cls(
            returncode=int(payload.get("returncode", 1)),
            stdout=str(payload.get("stdout", "")),
            stderr=str(payload.get("stderr", "")),
            args=[str(a) for a in payload.get("args", [])] if isinstance(payload.get("args"), list) else [],
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "args": list(self.args),
        }
