from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import os
import signal
from typing import Sequence


@dataclass
class ManagedProcess:
    name: str
    command: list[str]
    env_overrides: dict[str, str]
    process: asyncio.subprocess.Process


class ProcessSupervisor:
    def __init__(self, log_dir: Path) -> None:
        self._log_dir = log_dir
        self._processes: dict[str, ManagedProcess] = {}
        self._last_exit_codes: dict[str, int] = {}

    def running(self, name: str) -> bool:
        proc = self._processes.get(name)
        return bool(proc and proc.process.returncode is None)

    def get(self, name: str) -> ManagedProcess | None:
        return self._processes.get(name)

    async def start(self, name: str, command: Sequence[str], env: dict[str, str] | None = None) -> ManagedProcess:
        await self.stop(name)

        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        session_log = self._log_dir / f"{name}-{ts}.log"
        log_path = session_log
        log_file = open(log_path, "ab")
        try:
            proc_env = os.environ.copy()
            env_overrides: dict[str, str] = {}
            if env:
                env_overrides = {str(k): str(v) for k, v in env.items()}
                proc_env.update(env_overrides)
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=log_file,
                stderr=asyncio.subprocess.STDOUT,
                start_new_session=True,
                env=proc_env,
            )
        finally:
            log_file.close()
        managed = ManagedProcess(name=name, command=list(command), env_overrides=env_overrides, process=process)
        self._processes[name] = managed

        # Best-effort stable pointer to latest log
        latest = self._log_dir / f"{name}.log"
        try:
            if latest.exists() or latest.is_symlink():
                latest.unlink()
            os.symlink(session_log.name, latest)
        except Exception:
            pass

        return managed

    async def stop(self, name: str, graceful_timeout: float = 3.0, kill_timeout: float = 2.0) -> None:
        managed = self._processes.get(name)
        if not managed:
            return
        process = managed.process
        if process.returncode is not None:
            self._last_exit_codes[name] = int(process.returncode)
            self._processes.pop(name, None)
            return

        # Terminate the whole process group (backend tools may spawn children).
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except Exception:
            # Fallback to direct terminate.
            process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=graceful_timeout)
        except TimeoutError:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except Exception:
                process.kill()
            try:
                await asyncio.wait_for(process.wait(), timeout=kill_timeout)
            except TimeoutError:
                pass
        finally:
            if process.returncode is not None:
                self._last_exit_codes[name] = int(process.returncode)
            self._processes.pop(name, None)

    async def stop_all(self) -> None:
        for name in list(self._processes.keys()):
            await self.stop(name)

    async def wait(self, name: str) -> int | None:
        managed = self._processes.get(name)
        if not managed:
            return None
        rc = await managed.process.wait()
        self._last_exit_codes[name] = int(rc)
        return rc

    def last_exit_code(self, name: str) -> int | None:
        return self._last_exit_codes.get(name)

    def latest_log_path(self, name: str) -> str:
        return str(self._log_dir / f"{name}.log")
