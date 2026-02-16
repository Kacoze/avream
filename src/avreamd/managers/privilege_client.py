from __future__ import annotations

import asyncio
import contextlib
import json
import os
from pathlib import Path
import shutil
import stat
from uuid import uuid4

from avreamd.api.errors import backend_error, busy_device_error, permission_error, timeout_error, unsupported_error


class PrivilegeClient:
    ALLOWED_ACTIONS = {
        "noop",
        "v4l2.ensure_config",
        "v4l2.load",
        "v4l2.reload",
        "v4l2.status",
        "snd_aloop.load",
        "snd_aloop.unload",
        "snd_aloop.status",
    }

    def __init__(self, helper_bin: str | None = None) -> None:
        self.helper_bin = helper_bin or os.getenv("AVREAM_HELPER_BIN", "/usr/libexec/avream-helper")
        # Modes:
        # - auto: prefer pkexec when usable, else fall back to systemd-run
        # - pkexec: always use pkexec
        # - systemd-run: use systemd-run transient root unit (polkit)
        # - direct: run helper directly (dev only)
        self.mode = os.getenv("AVREAM_HELPER_MODE", "pkexec")
        self.timeout_s = float(os.getenv("AVREAM_HELPER_TIMEOUT", "15"))

    async def call(self, action: str, params: dict[str, object]) -> dict[str, object]:
        if action not in self.ALLOWED_ACTIONS:
            raise unsupported_error("unsupported privileged action", {"action": action})
        if not isinstance(params, dict):
            raise unsupported_error("privileged action params must be an object", {"action": action})

        helper_path = Path(self.helper_bin)
        if not helper_path.is_absolute():
            raise permission_error("helper path must be absolute", {"binary": self.helper_bin})

        request = {
            "request_id": str(uuid4()),
            "action": action,
            "params": params,
        }
        payload = json.dumps(request).encode("utf-8")

        cmd = self._helper_command()
        stdout, stderr, returncode, used_cmd = await self._exec_helper(cmd=cmd, payload=payload, action=action)

        if returncode != 0:
            stderr_text = stderr.decode("utf-8", errors="replace").strip()
            lower_stderr = stderr_text.lower()
            if (
                "pkexec must be setuid root" in lower_stderr
                and used_cmd
                and used_cmd[0] == "pkexec"
                and shutil.which("systemd-run")
            ):
                stdout, stderr, returncode, used_cmd = await self._exec_helper(
                    cmd=self._systemd_run_cmd(),
                    payload=payload,
                    action=action,
                )

        if returncode != 0:
            stderr_text = stderr.decode("utf-8", errors="replace").strip()
            lower_stderr = stderr_text.lower()
            if "pkexec must be setuid root" in lower_stderr:
                raise permission_error(
                    "pkexec is misconfigured (missing setuid root)",
                    {
                        "action": action,
                        "returncode": returncode,
                        "stderr": stderr_text,
                        "hint": "set AVREAM_HELPER_MODE=systemd-run or reinstall policykit-1 and verify /usr/bin/pkexec is root:root 4755",
                    },
                )
            if returncode in {126, 127} or "not authorized" in lower_stderr or "authentication" in lower_stderr:
                raise permission_error(
                    "authorization denied or cancelled",
                    {
                        "action": action,
                        "returncode": returncode,
                        "stderr": stderr_text,
                        "hint": "confirm polkit rule and complete authentication prompt",
                    },
                )
            raise permission_error(
                "privileged action failed",
                {"action": action, "returncode": returncode, "stderr": stderr_text},
            )

        try:
            response = json.loads(stdout.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise backend_error("invalid response from helper", {"action": action}) from exc

        if not response.get("ok", False):
            err = response.get("error") or {}
            code = err.get("code", "E_HELPER_FAILED")
            message = err.get("message", "helper action failed")
            if code == "E_BUSY_DEVICE":
                raise busy_device_error(
                    message,
                    {"action": action, "helper_code": code, "error": err},
                )
            if code in {"E_ACTION", "E_INVALID_PARAM"}:
                raise unsupported_error(message, {"action": action, "helper_code": code, "error": err})
            if code == "E_TIMEOUT":
                raise timeout_error(message, {"action": action, "helper_code": code, "error": err})
            raise backend_error(message, {"action": action, "helper_code": code, "error": err}, retryable=False)

        data = response.get("data", {})
        if not isinstance(data, dict):
            return {}
        return data

    async def _exec_helper(
        self,
        *,
        cmd: list[str],
        payload: bytes,
        action: str,
    ) -> tuple[bytes, bytes, int, list[str]]:
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise permission_error("privileged helper is not available", {"binary": cmd[0]}) from exc

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(payload), timeout=self.timeout_s)
        except TimeoutError as exc:
            with contextlib.suppress(Exception):
                proc.kill()
            raise timeout_error("privileged helper timed out", {"action": action, "timeout_s": self.timeout_s}) from exc

        return stdout, stderr, int(proc.returncode or 0), cmd

    def _helper_command(self) -> list[str]:
        mode = (self.mode or "auto").strip().lower()
        if mode == "direct":
            return [self.helper_bin]
        if mode == "pkexec":
            if self._pkexec_usable():
                return ["pkexec", self.helper_bin]
            if shutil.which("systemd-run"):
                return self._systemd_run_cmd()
            return ["pkexec", self.helper_bin]
        if mode == "systemd-run":
            return self._systemd_run_cmd()
        if mode != "auto":
            return ["pkexec", self.helper_bin]

        if self._pkexec_usable():
            return ["pkexec", self.helper_bin]
        if shutil.which("systemd-run"):
            return self._systemd_run_cmd()
        return ["pkexec", self.helper_bin]

    def diagnostics(self) -> dict[str, object]:
        cmd = self._helper_command()
        return {
            "configured_mode": (self.mode or "").strip().lower() or "pkexec",
            "effective_runner": cmd[0] if cmd else "unknown",
            "effective_command": cmd,
            "helper_bin": self.helper_bin,
            "pkexec_usable": self._pkexec_usable(),
            "systemd_run_available": bool(shutil.which("systemd-run")),
        }

    def _pkexec_usable(self) -> bool:
        pkexec_path = shutil.which("pkexec")
        if not pkexec_path:
            return False
        try:
            st = os.stat(pkexec_path)
        except Exception:
            return False
        return bool(st.st_mode & stat.S_ISUID)

    def _systemd_run_cmd(self) -> list[str]:
        return [
            "systemd-run",
            "--quiet",
            "--pipe",
            "--wait",
            "--collect",
            "-p",
            "Type=oneshot",
            "-p",
            "User=root",
            "-p",
            "Group=root",
            self.helper_bin,
        ]
