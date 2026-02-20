from __future__ import annotations

import asyncio
import os
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str
    args: list[str]

    def as_dict(self) -> dict[str, object]:
        return {
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "args": list(self.args),
        }


class CommandRunner:
    def __init__(self, *, env_overrides: dict[str, str] | None = None) -> None:
        self._env_overrides = dict(env_overrides or {})

    def _env(self) -> dict[str, str]:
        env = os.environ.copy()
        env.update(self._env_overrides)
        return env

    async def run_async(self, command: list[str]) -> CommandResult:
        proc = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._env(),
        )
        stdout, stderr = await proc.communicate()
        return CommandResult(
            returncode=int(proc.returncode or 0),
            stdout=stdout.decode("utf-8", errors="replace"),
            stderr=stderr.decode("utf-8", errors="replace"),
            args=list(command),
        )

    def run_sync(self, command: list[str]) -> CommandResult:
        proc = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            env=self._env(),
        )
        return CommandResult(
            returncode=int(proc.returncode or 0),
            stdout=str(proc.stdout or ""),
            stderr=str(proc.stderr or ""),
            args=list(command),
        )
