from __future__ import annotations

import subprocess


class RestartScheduler:
    def schedule_daemon_restart(self) -> None:
        cmd = [
            "bash",
            "-lc",
            "(sleep 1; systemctl --user restart avreamd.service) >/dev/null 2>&1 &",
        ]
        subprocess.Popen(cmd)
