from __future__ import annotations

import shutil
from typing import Sequence


class ScrcpyAdapter:
    def __init__(self, scrcpy_bin: str | None = None) -> None:
        self.scrcpy_bin = scrcpy_bin or shutil.which("scrcpy")

    @property
    def available(self) -> bool:
        return bool(self.scrcpy_bin)

    def command_for_android_camera(
        self,
        *,
        serial: str,
        sink_path: str,
        preset: str,
        camera_facing: str | None = None,
        preview_window: bool = False,
        enable_audio: bool = False,
        extra_args: Sequence[str] | None = None,
    ) -> list[str]:
        if not self.scrcpy_bin:
            raise RuntimeError("scrcpy not found")

        cmd = [
            self.scrcpy_bin,
            "-s",
            serial,
            "--video-source=camera",
            f"--v4l2-sink={sink_path}",
        ]

        if preview_window:
            cmd.extend([
                "--window-title=AVream Preview",
                "--window-width=640",
                "--window-height=360",
                "--no-control",
            ])
        else:
            cmd.append("--no-window")

        if camera_facing in {"front", "back"}:
            cmd.append(f"--camera-facing={camera_facing}")

        if enable_audio:
            cmd.append("--audio-source=mic")
        else:
            cmd.append("--no-audio")

        if preset == "low_latency":
            cmd.extend(["--max-fps=30", "--video-bit-rate=6M", "--v4l2-buffer=200"])
        elif preset == "high_quality":
            cmd.extend(["--video-bit-rate=12M", "--max-size=1440", "--v4l2-buffer=600"])
        else:
            cmd.extend(["--video-bit-rate=8M", "--max-size=1080", "--v4l2-buffer=400"])

        if extra_args:
            cmd.extend(extra_args)
        return cmd
