from __future__ import annotations

import os
import shutil
import subprocess


class PactlIntegration:
    def __init__(self) -> None:
        self.pactl = shutil.which("pactl")

    @property
    def available(self) -> bool:
        return bool(self.pactl)

    def _c_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["LC_ALL"] = "C"
        env["LANG"] = "C"
        return env

    def load_module(self, name: str, args: list[str]) -> int:
        if not self.pactl:
            raise FileNotFoundError("pactl not found")
        proc = subprocess.run(
            [self.pactl, "load-module", name, *args],
            check=False,
            capture_output=True,
            text=True,
            env=self._c_env(),
        )
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "").strip() or "pactl load-module failed")
        out = (proc.stdout or "").strip()
        return int(out)

    def unload_module(self, module_id: int) -> None:
        if not self.pactl:
            raise FileNotFoundError("pactl not found")
        subprocess.run([self.pactl, "unload-module", str(module_id)], check=False, env=self._c_env())

    def list_modules(self) -> list[dict[str, str]]:
        if not self.pactl:
            raise FileNotFoundError("pactl not found")
        proc = subprocess.run(
            [self.pactl, "list", "short", "modules"],
            check=False,
            capture_output=True,
            text=True,
            env=self._c_env(),
        )
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "").strip() or "pactl list modules failed")

        modules: list[dict[str, str]] = []
        for line in (proc.stdout or "").splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            module_id = parts[0].strip()
            name = parts[1].strip()
            args = parts[2].strip() if len(parts) >= 3 else ""
            modules.append({"id": module_id, "name": name, "args": args})
        return modules

    def info(self) -> dict[str, str]:
        if not self.pactl:
            raise FileNotFoundError("pactl not found")
        proc = subprocess.run(
            [self.pactl, "info"],
            check=False,
            capture_output=True,
            text=True,
            env=self._c_env(),
        )
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "").strip() or "pactl info failed")

        out: dict[str, str] = {}
        for line in (proc.stdout or "").splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            out[key.strip()] = value.strip()
        return out

    def default_source(self) -> str | None:
        try:
            info = self.info()
        except Exception:
            return None
        source = info.get("Default Source")
        if not source:
            return None
        return source

    def list_sources(self) -> list[str]:
        if not self.pactl:
            raise FileNotFoundError("pactl not found")
        proc = subprocess.run(
            [self.pactl, "list", "short", "sources"],
            check=False,
            capture_output=True,
            text=True,
            env=self._c_env(),
        )
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "").strip() or "pactl list sources failed")

        names: list[str] = []
        for line in (proc.stdout or "").splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            name = parts[1].strip()
            if name:
                names.append(name)
        return names

    def list_sink_inputs_detailed(self) -> list[dict[str, object]]:
        if not self.pactl:
            raise FileNotFoundError("pactl not found")
        proc = subprocess.run(
            [self.pactl, "list", "sink-inputs"],
            check=False,
            capture_output=True,
            text=True,
            env=self._c_env(),
        )
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "").strip() or "pactl list sink-inputs failed")

        inputs: list[dict[str, object]] = []
        current: dict[str, object] | None = None
        in_props = False
        for raw in (proc.stdout or "").splitlines():
            line = raw.rstrip("\n")
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("Sink Input #"):
                if current is not None:
                    inputs.append(current)
                sid = stripped.split("#", 1)[1].strip()
                current = {"id": sid, "properties": {}}
                in_props = False
                continue
            if current is None:
                continue
            if stripped.startswith("Sink:"):
                current["sink"] = stripped.split(":", 1)[1].strip()
                continue
            if stripped.startswith("Properties:"):
                in_props = True
                continue

            if in_props:
                # Expected format: key = "value"
                if " = " not in stripped:
                    # likely next section
                    in_props = False
                    continue
                key, value = stripped.split(" = ", 1)
                value = value.strip()
                if value.startswith('"') and value.endswith('"') and len(value) >= 2:
                    value = value[1:-1]
                props = current.get("properties")
                if isinstance(props, dict):
                    props[key.strip()] = value

        if current is not None:
            inputs.append(current)
        return inputs

    def move_sink_input(self, sink_input_id: int, sink_name: str) -> None:
        if not self.pactl:
            raise FileNotFoundError("pactl not found")
        proc = subprocess.run(
            [self.pactl, "move-sink-input", str(int(sink_input_id)), sink_name],
            check=False,
            capture_output=True,
            text=True,
            env=self._c_env(),
        )
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "").strip() or "pactl move-sink-input failed")
