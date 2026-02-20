from __future__ import annotations

import asyncio
from typing import Any

from avreamd.integrations.pactl import PactlIntegration


class ScrcpyAudioRouter:
    def __init__(self, *, pactl: PactlIntegration, sink_name: str) -> None:
        self._pactl = pactl
        self._sink_name = sink_name
        self._task: asyncio.Task | None = None

    async def move_once(self) -> dict[str, Any]:
        if not self._pactl.available:
            return {"moved": 0, "attempts": 0, "reason": "pactl_unavailable"}

        moved = 0
        attempts = 0
        last_error: str | None = None
        for _ in range(12):
            attempts += 1
            try:
                sink_inputs = self._pactl.list_sink_inputs_detailed()
            except Exception as exc:
                last_error = str(exc)
                await asyncio.sleep(0.2)
                continue

            scrcpy_ids: list[int] = []
            for entry in sink_inputs:
                sid_raw = entry.get("id")
                sid = int(sid_raw) if isinstance(sid_raw, str) and sid_raw.isdigit() else None
                if sid is None:
                    continue
                props = entry.get("properties")
                app_blob = ""
                if isinstance(props, dict):
                    app_blob = " ".join(
                        [
                            str(props.get("application.name", "")),
                            str(props.get("application.process.binary", "")),
                            str(props.get("media.name", "")),
                        ]
                    ).lower()
                if "scrcpy" in app_blob:
                    scrcpy_ids.append(sid)

            if not scrcpy_ids:
                await asyncio.sleep(0.2)
                continue

            for sid in scrcpy_ids:
                try:
                    self._pactl.move_sink_input(sid, self._sink_name)
                    moved += 1
                except Exception as exc:
                    last_error = str(exc)

            return {
                "moved": moved,
                "attempts": attempts,
                "matched": len(scrcpy_ids),
                "error": last_error,
            }

        return {"moved": moved, "attempts": attempts, "matched": 0, "error": last_error}

    def start_background(self, *, is_active) -> None:
        self.stop_background()

        async def runner() -> None:
            while True:
                try:
                    if not bool(is_active()):
                        return
                    await self.move_once()
                    await asyncio.sleep(0.8)
                except asyncio.CancelledError:
                    return
                except Exception:
                    await asyncio.sleep(1.0)

        self._task = asyncio.create_task(runner())

    def stop_background(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None
