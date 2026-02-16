from __future__ import annotations

import shutil
import subprocess


class PipeWireIntegration:
    def __init__(self) -> None:
        self.pw_cli = shutil.which("pw-cli")
        self.pactl = shutil.which("pactl")
        self.pw_loopback = shutil.which("pw-loopback")

    def available(self) -> bool:
        return bool(self.pw_cli or self.pactl or self.pw_loopback)

    def running(self) -> bool:
        if self.pw_cli:
            proc = subprocess.run([self.pw_cli, "info", "0"], check=False, capture_output=True)
            if proc.returncode == 0:
                return True
        if self.pactl:
            proc = subprocess.run([self.pactl, "info"], check=False, capture_output=True)
            return proc.returncode == 0
        return False

    def supports_native_virtual_mic(self) -> bool:
        return bool(self.pw_loopback and self.running())

    def node_exists(self, node_name: str) -> bool:
        if not self.pw_cli:
            return False
        proc = subprocess.run([self.pw_cli, "ls", "Node"], check=False, capture_output=True, text=True)
        if proc.returncode != 0:
            return False
        return f'node.name = "{node_name}"' in proc.stdout
