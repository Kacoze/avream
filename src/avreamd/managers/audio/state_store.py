from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class AudioStateRepository:
    def __init__(self, *, state_file: Path) -> None:
        self._state_file = state_file

    def load(self) -> dict[str, Any]:
        try:
            data = json.loads(self._state_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
            return {}
        except Exception:  # state file may be absent or corrupt on first run
            return {}

    def save(self, data: dict[str, Any]) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def clear(self) -> None:
        try:
            if self._state_file.exists():
                self._state_file.unlink()
        except Exception:  # best-effort cleanup; file may already be absent
            pass
