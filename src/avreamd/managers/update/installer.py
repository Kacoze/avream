from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Any

from avreamd.api.errors import backend_error, dependency_error, validation_error


class PackageInstaller:
    def __init__(self, *, install_tool: str) -> None:
        self._install_tool = install_tool

    async def run_install(self, deb_path: Path) -> dict[str, Any]:
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
