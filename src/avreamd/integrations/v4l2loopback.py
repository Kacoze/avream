from __future__ import annotations

from pathlib import Path
import subprocess


class V4L2LoopbackIntegration:
    def __init__(self, video_nr: int = 10) -> None:
        self.video_nr = video_nr

    @property
    def device_path(self) -> Path:
        return Path(f"/dev/video{self.video_nr}")

    def module_loaded(self) -> bool:
        try:
            with open("/proc/modules", "r", encoding="utf-8") as handle:
                for line in handle:
                    if line.startswith("v4l2loopback "):
                        return True
        except FileNotFoundError:
            return False
        return False

    def device_exists(self) -> bool:
        return self.device_path.exists()

    def device_busy(self) -> bool:
        cmd = ["fuser", str(self.device_path)]
        try:
            proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
        except FileNotFoundError:
            return False
        return proc.returncode == 0 and bool(proc.stdout.strip() or proc.stderr.strip())

    def device_blockers(self) -> list[int]:
        cmd = ["fuser", str(self.device_path)]
        try:
            proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
        except FileNotFoundError:
            return []
        if proc.returncode != 0:
            return []
        raw = (proc.stdout or proc.stderr or "").strip()
        pids: list[int] = []
        for token in raw.replace(":", " ").split():
            try:
                pids.append(int(token))
            except ValueError:
                continue
        return sorted(set(pids))
