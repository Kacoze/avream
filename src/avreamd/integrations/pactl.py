from __future__ import annotations

import shutil

from avreamd.integrations.command_runner import CommandRunner


class PactlIntegration:
    def __init__(self) -> None:
        self.pactl = shutil.which("pactl")
        self._runner = CommandRunner(env_overrides={"LC_ALL": "C", "LANG": "C"})

    @property
    def available(self) -> bool:
        return bool(self.pactl)

    def load_module(self, name: str, args: list[str]) -> int:
        if not self.pactl:
            raise FileNotFoundError("pactl not found")
        result = self._runner.run_sync([self.pactl, "load-module", name, *args])
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "").strip() or "pactl load-module failed")
        out = (result.stdout or "").strip()
        return int(out)

    def unload_module(self, module_id: int) -> None:
        if not self.pactl:
            raise FileNotFoundError("pactl not found")
        _ = self._runner.run_sync([self.pactl, "unload-module", str(module_id)])

    def list_modules(self) -> list[dict[str, str]]:
        if not self.pactl:
            raise FileNotFoundError("pactl not found")
        result = self._runner.run_sync([self.pactl, "list", "short", "modules"])
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "").strip() or "pactl list modules failed")

        modules: list[dict[str, str]] = []
        for line in (result.stdout or "").splitlines():
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
        result = self._runner.run_sync([self.pactl, "info"])
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "").strip() or "pactl info failed")

        out: dict[str, str] = {}
        for line in (result.stdout or "").splitlines():
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
        result = self._runner.run_sync([self.pactl, "list", "short", "sources"])
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "").strip() or "pactl list sources failed")

        names: list[str] = []
        for line in (result.stdout or "").splitlines():
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
        result = self._runner.run_sync([self.pactl, "list", "sink-inputs"])
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "").strip() or "pactl list sink-inputs failed")

        inputs: list[dict[str, object]] = []
        current: dict[str, object] | None = None
        in_props = False
        for raw in (result.stdout or "").splitlines():
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
        result = self._runner.run_sync([self.pactl, "move-sink-input", str(int(sink_input_id)), sink_name])
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "").strip() or "pactl move-sink-input failed")
