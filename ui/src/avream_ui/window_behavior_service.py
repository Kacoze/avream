from __future__ import annotations

from gi.repository import GLib  # type: ignore[import-not-found]


class WindowServiceMixin:
    def _set_daemon_lock(self, locked: bool, message: str | None = None) -> None:
        self._daemon_locked = locked
        if locked:
            self.main_stack.set_visible_child_name("daemon-lock")
            self.lock_status_label.set_text(
                message
                or "AVream daemon service is not active for this user session. Enable the service and retry."
            )
        else:
            self.main_stack.set_visible_child_name("main")
        self._set_busy(self._busy)

    def _service_enable_commands(self) -> str:
        return (
            "mkdir -p ~/.config/avream\n"
            "cp -n /usr/lib/systemd/user/avreamd.env ~/.config/avream/avreamd.env\n"
            "systemctl --user daemon-reload\n"
            "systemctl --user enable --now avreamd.service"
        )

    def _on_show_manual_commands(self, _btn) -> None:
        self._show_info_dialog("Manual setup commands", self._service_enable_commands())

    def _on_retry_service(self, _btn) -> None:
        self._refresh_status()

    def _wait_for_daemon_ready(self, attempts: int = 60, interval_ms: int = 500) -> None:
        state = {"remaining": attempts}
        self.lock_status_label.set_text("Service enabled. Waiting for daemon startup...")

        def tick() -> bool:
            self._refresh_status()
            if not self._daemon_locked:
                self._append_log("AVream daemon is ready.")
                self._set_busy(False)
                return False

            state["remaining"] -= 1
            if state["remaining"] <= 0:
                self._set_busy(False)
                self._append_log("Daemon did not become ready before timeout.")
                self.lock_status_label.set_text(
                    "Service was enabled, but daemon is still unreachable. Click Retry or use manual commands."
                )
                return False

            done = attempts - state["remaining"]
            self.lock_status_label.set_text(f"Service enabled. Waiting for daemon startup... ({done}/{attempts})")
            return True

        GLib.idle_add(tick)
        GLib.timeout_add(interval_ms, tick)

    def _on_enable_service(self, _btn) -> None:
        self._set_busy(True)
        self.progress_label.set_text("Enabling AVream daemon service...")

        command = [
            "bash",
            "-lc",
            (
                "set -e; "
                "mkdir -p ~/.config/avream; "
                "if [ -f /usr/lib/systemd/user/avreamd.env ]; then "
                "cp -n /usr/lib/systemd/user/avreamd.env ~/.config/avream/avreamd.env || true; "
                "fi; "
                "systemctl --user daemon-reload; "
                "systemctl --user reset-failed avreamd.service || true; "
                "systemctl --user enable avreamd.service; "
                "systemctl --user start avreamd.service"
            ),
        ]

        def done(result: dict) -> bool:
            self.progress_label.set_text("")
            if not result.get("ok"):
                self._set_busy(False)
                stderr = str(result.get("stderr", "")).strip() or "service enable failed"
                self._append_log(f"service enable failed: {stderr}")
                self._show_error_dialog(
                    "Enable service failed",
                    f"{stderr}\n\nRun manually:\n{self._service_enable_commands()}",
                )
                return False

            self._append_log("AVream daemon service enabled.")
            self._wait_for_daemon_ready()
            return False

        self._run_cmd_async(command, done)

    def _on_refresh(self, _btn) -> None:
        self._refresh_status()

    def _on_stream_toggle(self, _btn) -> None:
        if self._video_running:
            self._on_video_stop(_btn)
            return
        self._on_phone_start(_btn)

    def _on_video_stop(self, _btn) -> None:
        self._set_busy(True)
        self.progress_label.set_text("Stopping camera...")
        self._call_async("POST", "/video/stop", {}, self._after_action)

    def _on_video_reset(self, _btn) -> None:
        def do_reset() -> None:
            self._set_busy(True)
            self.progress_label.set_text("Resetting camera...")
            self._call_async("POST", "/video/reset", {"force": False}, self._after_action)

        self._confirm("Reset camera", "This reloads the virtual camera device. Continue?", do_reset)
