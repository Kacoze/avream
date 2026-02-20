from __future__ import annotations

import subprocess
import threading
from typing import Any, Callable

from gi.repository import GLib  # type: ignore[import-not-found]

from avream_ui.api_client import ApiClient


class WindowServices:
    def __init__(self, *, api: ApiClient, logger: Callable[[str], None]) -> None:
        self._api = api
        self._logger = logger

    @property
    def socket_path(self) -> str:
        return self._api.socket_path

    def call(self, method: str, path: str, payload: dict | None = None) -> dict[str, Any]:
        try:
            result = self._api.request_sync(method, path, payload)
            self._log(f"{method} {path} -> HTTP {result['status']}")
            return {
                "status": result.get("status"),
                "body": result.get("body"),
                "_meta": {"method": method, "path": path, "payload": payload or {}},
            }
        except Exception as exc:
            self._log(f"{method} {path} failed: {exc}")
            return {
                "status": 0,
                "body": {
                    "ok": False,
                    "error": {
                        "code": "E_DAEMON_UNREACHABLE",
                        "message": str(exc),
                        "details": {"socket_path": self._api.socket_path},
                    },
                },
                "_meta": {"method": method, "path": path, "payload": payload or {}},
            }

    def _log(self, text: str) -> None:
        GLib.idle_add(self._logger, text)

    def call_async(self, method: str, path: str, payload: dict | None, on_done) -> None:
        def run() -> None:
            result = self.call(method, path, payload)
            GLib.idle_add(on_done, result)

        threading.Thread(target=run, daemon=True).start()

    @staticmethod
    def run_cmd_async(command: list[str], on_done) -> None:
        def run() -> None:
            try:
                proc = subprocess.run(command, capture_output=True, text=True, check=False)
                result = {
                    "ok": proc.returncode == 0,
                    "returncode": proc.returncode,
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                    "command": command,
                }
            except Exception as exc:
                result = {
                    "ok": False,
                    "returncode": -1,
                    "stdout": "",
                    "stderr": str(exc),
                    "command": command,
                }
            GLib.idle_add(on_done, result)

        threading.Thread(target=run, daemon=True).start()
