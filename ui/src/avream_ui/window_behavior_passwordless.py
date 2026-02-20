from __future__ import annotations

import json
import os
import shutil


class WindowPasswordlessMixin:
    def _passwordless_tool(self) -> str | None:
        env_path = os.getenv("AVREAM_PASSWORDLESS_TOOL")
        if env_path and os.path.isfile(env_path) and os.access(env_path, os.X_OK):
            return env_path

        for path in (
            "/usr/bin/avream-passwordless-setup",
            "/usr/local/bin/avream-passwordless-setup",
            "scripts/avream-passwordless-setup.sh",
        ):
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path

        return shutil.which("avream-passwordless-setup")

    def _run_cmd_async(self, command: list[str], on_done) -> None:
        self.services.run_cmd_async(command, on_done)

    def _username(self) -> str:
        return os.getenv("USER", "")

    def _refresh_passwordless_status(self) -> None:
        tool = self._passwordless_tool()
        if not tool:
            self.passwordless_status_label.set_text("Passwordless setup tool is not installed.")
            self._append_log("passwordless status: tool not found")
            return
        user = self._username()
        if not user:
            self.passwordless_status_label.set_text("Cannot detect current username.")
            self._append_log("passwordless status: username missing")
            return

        self.progress_label.set_text("Checking passwordless status...")
        cmd = [tool, "status", "--user", user, "--json"]

        def done(result: dict) -> bool:
            self.progress_label.set_text("")
            if not result.get("ok"):
                stderr = str(result.get("stderr", "")).strip() or "status command failed"
                self.passwordless_status_label.set_text(f"Passwordless status error: {stderr}")
                self._append_log(f"passwordless status failed: {stderr}")
                self._show_error_dialog("Passwordless status failed", stderr)
                return False
            try:
                payload = json.loads(str(result.get("stdout", "{}")))
            except Exception:
                self.passwordless_status_label.set_text("Passwordless status parse error.")
                self._append_log("passwordless status parse error")
                self._show_error_dialog("Passwordless status failed", "Could not parse status output.")
                return False
            enabled = bool(payload.get("enabled", False))
            runner = "unknown"

            def done_status(status_resp: dict) -> bool:
                status_body = status_resp.get("body", {})
                nonlocal runner
                if isinstance(status_body, dict) and status_body.get("ok"):
                    data = status_body.get("data", {})
                    service = data.get("service", {}) if isinstance(data, dict) else {}
                    helper = service.get("helper", {}) if isinstance(service, dict) else {}
                    if isinstance(helper, dict):
                        runner = str(helper.get("effective_runner", "unknown"))

                if enabled and runner == "pkexec":
                    self.passwordless_status_label.set_text("Passwordless helper actions are enabled (runner: pkexec).")
                    self._append_log("passwordless status: enabled, runner=pkexec")
                elif enabled and runner != "pkexec":
                    self.passwordless_status_label.set_text(
                        f"Passwordless is enabled but daemon runner is '{runner}'. Set AVREAM_HELPER_MODE=pkexec and restart avreamd."
                    )
                    self._append_log(f"passwordless status: enabled but runner={runner}")
                else:
                    self.passwordless_status_label.set_text("Passwordless helper actions are disabled.")
                    self._append_log("passwordless status: disabled")
                return False

            self._call_async("GET", "/status", None, done_status)
            return False

        self._run_cmd_async(cmd, done)

    def _on_passwordless_status(self, _btn) -> None:
        self._refresh_passwordless_status()

    def _on_passwordless_enable(self, _btn) -> None:
        tool = self._passwordless_tool()
        user = self._username()
        if not tool:
            self._show_error_dialog("Tool not found", "avream-passwordless-setup is not installed.")
            return
        if not user:
            self._show_error_dialog("User unknown", "Cannot detect current username.")
            return
        if not shutil.which("pkexec"):
            self._show_error_dialog("pkexec missing", "Install policykit-1 (pkexec) to run this action from GUI.")
            return

        def do_enable() -> None:
            self._set_busy(True)
            self.progress_label.set_text("Enabling passwordless helper actions...")
            cmd = ["pkexec", tool, "enable", "--user", user]

            def done(result: dict) -> bool:
                self._set_busy(False)
                self.progress_label.set_text("")
                if not result.get("ok"):
                    msg = str(result.get("stderr", "")).strip() or "enable failed"
                    self._show_error_dialog("Enable failed", msg)
                    return False
                self._append_log("Passwordless helper actions enabled")
                self._show_error_dialog(
                    "Enabled",
                    "Passwordless helper actions were enabled. Log out and log in again to refresh group membership.",
                )
                self._refresh_passwordless_status()
                return False

            self._run_cmd_async(cmd, done)

        self._confirm(
            "Enable passwordless mode",
            "This allows your local active user session to run AVream helper actions without password prompt. Continue?",
            do_enable,
        )

    def _on_passwordless_disable(self, _btn) -> None:
        tool = self._passwordless_tool()
        user = self._username()
        if not tool:
            self._show_error_dialog("Tool not found", "avream-passwordless-setup is not installed.")
            return
        if not user:
            self._show_error_dialog("User unknown", "Cannot detect current username.")
            return
        if not shutil.which("pkexec"):
            self._show_error_dialog("pkexec missing", "Install policykit-1 (pkexec) to run this action from GUI.")
            return

        def do_disable() -> None:
            self._set_busy(True)
            self.progress_label.set_text("Disabling passwordless helper actions...")
            cmd = ["pkexec", tool, "disable", "--user", user]

            def done(result: dict) -> bool:
                self._set_busy(False)
                self.progress_label.set_text("")
                if not result.get("ok"):
                    msg = str(result.get("stderr", "")).strip() or "disable failed"
                    self._show_error_dialog("Disable failed", msg)
                    return False
                self._append_log("Passwordless helper actions disabled")
                self._show_error_dialog("Disabled", "Passwordless helper actions were disabled.")
                self._refresh_passwordless_status()
                return False

            self._run_cmd_async(cmd, done)

        self._confirm(
            "Disable passwordless mode",
            "This restores password prompts for AVream helper actions. Continue?",
            do_disable,
        )
