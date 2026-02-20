from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class ScrcpyPreset:
    video_bit_rate: str
    max_size: int | None
    max_fps: int | None
    v4l2_buffer: int


class ScrcpyAdapter:
    PRESETS: dict[str, ScrcpyPreset] = {
        "low_latency": ScrcpyPreset(video_bit_rate="6M", max_size=None, max_fps=30, v4l2_buffer=200),
        "balanced": ScrcpyPreset(video_bit_rate="8M", max_size=1080, max_fps=None, v4l2_buffer=400),
        "high_quality": ScrcpyPreset(video_bit_rate="12M", max_size=1440, max_fps=None, v4l2_buffer=600),
    }

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
        camera_rotation: int | None = None,
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

        if camera_rotation in {0, 90, 180, 270}:
            cmd.append(f"--capture-orientation={camera_rotation}")

        cmd.append("--camera-ar=16:9")

        if enable_audio:
            cmd.append("--audio-source=mic")
        else:
            cmd.append("--no-audio")

        selected = self.PRESETS.get(preset, self.PRESETS["balanced"])
        cmd.append(f"--video-bit-rate={selected.video_bit_rate}")
        if selected.max_size is not None:
            cmd.append(f"--max-size={selected.max_size}")
        if selected.max_fps is not None:
            cmd.append(f"--max-fps={selected.max_fps}")
        cmd.append(f"--v4l2-buffer={selected.v4l2_buffer}")

        if extra_args:
            cmd.extend(extra_args)
        return cmd
