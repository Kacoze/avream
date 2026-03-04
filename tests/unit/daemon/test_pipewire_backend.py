from __future__ import annotations

import unittest
from typing import Any, cast

from avreamd.api.errors import ApiError
from avreamd.managers.audio.backends.pipewire import PipeWireAudioBackend


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------

class _PactlStub:
    """Configurable pactl stub."""

    def __init__(
        self,
        *,
        available: bool = True,
        modules: list[dict[str, str]] | None = None,
        fail_load: bool = False,
        fail_on_second_load: bool = False,
    ) -> None:
        self._available = available
        self._modules = modules or []
        self._fail_load = fail_load
        self._fail_on_second_load = fail_on_second_load
        self._load_count = 0
        self.loaded: list[tuple[str, list[str]]] = []
        self.unloaded: list[int] = []
        self._next_id = 100

    @property
    def available(self) -> bool:
        return self._available

    def load_module(self, name: str, args: list[str]) -> int:
        self._load_count += 1
        if self._fail_load:
            raise RuntimeError("load-module failed")
        if self._fail_on_second_load and self._load_count >= 2:
            raise RuntimeError("second load-module failed")
        mid = self._next_id
        self._next_id += 1
        self.loaded.append((name, args))
        return mid

    def unload_module(self, module_id: int) -> None:
        self.unloaded.append(module_id)

    def list_modules(self) -> list[dict[str, str]]:
        if not self._available:
            raise FileNotFoundError("pactl not found")
        return list(self._modules)

    def list_sink_inputs_detailed(self) -> list[dict[str, Any]]:
        return []

    def move_sink_input(self, sink_input_id: int, sink_name: str) -> None:
        pass

    def default_source(self) -> str | None:
        return None

    def list_sources(self) -> list[str]:
        return []


class _PipewireStub:
    """PipeWire stub that only supports the pactl path."""

    pw_loopback: str | None = None

    def supports_native_virtual_mic(self) -> bool:
        return False

    def available(self) -> bool:
        return False

    def running(self) -> bool:
        return False


class _FastRouterStub:
    """Router stub that returns immediately."""

    async def move_once(self) -> dict[str, Any]:
        return {"moved": 0, "attempts": 0, "matched": 0, "error": None}

    def start_background(self, *, is_active: Any) -> None:
        pass

    def stop_background(self) -> None:
        pass


def _make_backend(
    pactl: _PactlStub,
    *,
    sink_name: str = "avream_sink",
    source_name: str = "avream_mic",
) -> PipeWireAudioBackend:
    backend = PipeWireAudioBackend(
        pipewire=cast(Any, _PipewireStub()),
        pactl=cast(Any, pactl),
        sink_name=sink_name,
        source_name=source_name,
    )
    # Replace router with a fast stub so tests don't block on move_once() retries.
    backend._router = cast(Any, _FastRouterStub())  # type: ignore[assignment]
    return backend


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class PipeWireAudioBackendTests(unittest.IsolatedAsyncioTestCase):

    # -- cleanup_stale_pactl_modules --

    def test_cleanup_removes_avream_modules_only(self) -> None:
        pactl = _PactlStub(
            modules=[
                {"id": "5", "name": "module-null-sink", "args": "sink_name=avream_sink something"},
                {"id": "6", "name": "module-remap-source", "args": "source_name=avream_mic other"},
                {"id": "7", "name": "module-loopback", "args": "unrelated_sink unrelated"},
            ]
        )
        backend = _make_backend(pactl)
        removed = backend.cleanup_stale_pactl_modules()
        self.assertEqual(sorted(removed), [5, 6])
        self.assertIn(5, pactl.unloaded)
        self.assertIn(6, pactl.unloaded)
        self.assertNotIn(7, pactl.unloaded)

    def test_cleanup_returns_empty_when_pactl_unavailable(self) -> None:
        pactl = _PactlStub(available=False)
        backend = _make_backend(pactl)
        result = backend.cleanup_stale_pactl_modules()
        self.assertEqual(result, [])

    def test_cleanup_returns_empty_when_no_avream_modules(self) -> None:
        pactl = _PactlStub(
            modules=[
                {"id": "3", "name": "module-alsa-card", "args": "device=hw:0"},
            ]
        )
        backend = _make_backend(pactl)
        result = backend.cleanup_stale_pactl_modules()
        self.assertEqual(result, [])

    # -- start() via pactl path --

    async def test_start_with_pactl_loads_sink_and_source(self) -> None:
        pactl = _PactlStub()
        backend = _make_backend(pactl)
        result = await backend.start(is_active=lambda: True)
        self.assertEqual(result["backend"], "pipewire")
        self.assertEqual(len(result["modules"]), 2)
        self.assertEqual(len(pactl.loaded), 2)
        names = [name for name, _ in pactl.loaded]
        self.assertIn("module-null-sink", names)
        self.assertIn("module-remap-source", names)

    async def test_start_rolls_back_on_source_load_failure(self) -> None:
        pactl = _PactlStub(fail_on_second_load=True)
        backend = _make_backend(pactl)
        with self.assertRaises(ApiError) as ctx:
            await backend.start(is_active=lambda: True)
        self.assertEqual(ctx.exception.code, "E_DEP_MISSING")
        # Sink module (first load) should have been rolled back
        self.assertGreaterEqual(len(pactl.unloaded), 1)

    async def test_start_raises_when_pactl_unavailable_and_no_pw_loopback(self) -> None:
        pactl = _PactlStub(available=False)
        backend = _make_backend(pactl)
        with self.assertRaises(ApiError) as ctx:
            await backend.start(is_active=lambda: True)
        self.assertEqual(ctx.exception.code, "E_DEP_MISSING")

    # -- stop() --

    async def test_stop_unloads_modules_from_state(self) -> None:
        pactl = _PactlStub()
        backend = _make_backend(pactl)
        state: dict[str, Any] = {"modules": [10, 11], "backend": "pipewire"}
        await backend.stop(state=state)
        self.assertIn(10, pactl.unloaded)
        self.assertIn(11, pactl.unloaded)

    async def test_stop_handles_empty_modules_gracefully(self) -> None:
        pactl = _PactlStub()
        backend = _make_backend(pactl)
        # Should not raise
        await backend.stop(state={"modules": [], "backend": "pipewire"})
        await backend.stop(state={})


if __name__ == "__main__":
    unittest.main()
