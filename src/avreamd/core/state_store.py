from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import asyncio
from typing import Any


class SubsystemState(str, Enum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    ERROR = "ERROR"


VALID_TRANSITIONS = {
    SubsystemState.STOPPED: {SubsystemState.STARTING},
    SubsystemState.STARTING: {SubsystemState.RUNNING, SubsystemState.STOPPING, SubsystemState.ERROR},
    SubsystemState.RUNNING: {SubsystemState.STOPPING, SubsystemState.ERROR},
    SubsystemState.STOPPING: {SubsystemState.STOPPED, SubsystemState.ERROR},
    SubsystemState.ERROR: {SubsystemState.STOPPED, SubsystemState.STARTING},
}


@dataclass
class SubsystemStatus:
    state: SubsystemState = SubsystemState.STOPPED
    operation_id: int = 0
    last_error: dict[str, Any] | None = None


@dataclass
class RuntimeStatus:
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    video: SubsystemStatus = field(default_factory=SubsystemStatus)
    audio: SubsystemStatus = field(default_factory=SubsystemStatus)


class InvalidTransitionError(ValueError):
    pass


class DaemonStateStore:
    def __init__(self) -> None:
        self._state = RuntimeStatus()
        self._lock = asyncio.Lock()

    async def snapshot(self) -> dict[str, Any]:
        async with self._lock:
            return {
                "started_at": self._state.started_at.isoformat(),
                "video": {
                    "state": self._state.video.state.value,
                    "operation_id": self._state.video.operation_id,
                    "last_error": self._state.video.last_error,
                },
                "audio": {
                    "state": self._state.audio.state.value,
                    "operation_id": self._state.audio.operation_id,
                    "last_error": self._state.audio.last_error,
                },
            }

    async def transition_video(self, next_state: SubsystemState) -> int:
        async with self._lock:
            self._transition(self._state.video, next_state, subsystem_name="video")
            return self._state.video.operation_id

    async def transition_audio(self, next_state: SubsystemState) -> int:
        async with self._lock:
            self._transition(self._state.audio, next_state, subsystem_name="audio")
            return self._state.audio.operation_id

    async def set_video_error(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        async with self._lock:
            self._state.video.last_error = {
                "code": code,
                "message": message,
                "details": details or {},
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            self._state.video.state = SubsystemState.ERROR
            self._state.video.operation_id += 1

    async def set_audio_error(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        async with self._lock:
            self._state.audio.last_error = {
                "code": code,
                "message": message,
                "details": details or {},
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            self._state.audio.state = SubsystemState.ERROR
            self._state.audio.operation_id += 1

    def _transition(self, target: SubsystemStatus, next_state: SubsystemState, subsystem_name: str) -> None:
        current = target.state
        if current == next_state:
            return

        allowed = VALID_TRANSITIONS.get(current, set())
        if next_state not in allowed:
            raise InvalidTransitionError(
                f"invalid {subsystem_name} transition {current.value} -> {next_state.value}"
            )

        target.state = next_state
        target.operation_id += 1
        if next_state != SubsystemState.ERROR:
            target.last_error = None
