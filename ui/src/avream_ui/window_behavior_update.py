from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

from gi.repository import Adw  # type: ignore[import-not-found]

try:
    from avreamd import __version__ as AVREAM_VERSION
except Exception:
    AVREAM_VERSION = "unknown"


class WindowUpdateMixin:
    def _candidate_cli_readme_paths(self) -> list[Path]:
        cwd = Path.cwd()
        return [
            Path("/usr/share/doc/avream/CLI_README.md"),
            cwd / "dist" / "CLI_README.md",
            cwd / "docs" / "CLI_README.md",
        ]

    def _on_open_cli_readme(self, _btn) -> None:
        readme_path = None
        for candidate in self._candidate_cli_readme_paths():
            if candidate.exists() and candidate.is_file():
                readme_path = candidate
                break
        if readme_path is None:
            self._show_error_dialog("README not found", "Could not find CLI README file on this system.")
            return

        opener = shutil.which("xdg-open")
        if not opener:
            self._show_error_dialog("xdg-open missing", f"Open this file manually: {readme_path}")
            return
        try:
            subprocess.Popen([opener, str(readme_path)])
            self._append_log(f"Opened CLI README: {readme_path}")
        except Exception as exc:
            self._show_error_dialog("Failed to open README", str(exc))

    def _apply_version_indicator(self, *, current: str, latest: str | None, available: bool) -> None:
        current_s = current if isinstance(current, str) and current else AVREAM_VERSION
        if available and isinstance(latest, str) and latest:
            self.version_btn.set_label(f"{current_s} -> {latest}")
            self.version_btn.set_tooltip_text("Update available. Click to open update modal.")
            self.version_btn.add_css_class("destructive-action")
        else:
            self.version_btn.set_label(current_s)
            self.version_btn.set_tooltip_text("Click to check for updates")
            self.version_btn.remove_css_class("destructive-action")

    def _open_release_url(self, url: str | None = None) -> None:
        target = url if isinstance(url, str) and url else self._latest_release_url
        opener = shutil.which("xdg-open")
        if not opener:
            self._show_error_dialog("xdg-open missing", f"Open this URL manually: {target}")
            return
        try:
            subprocess.Popen([opener, target])
            self._append_log(f"Opened release page: {target}")
        except Exception as exc:
            self._show_error_dialog("Failed to open release page", str(exc))

    def _run_update_install_with_confirm(self) -> None:
        def do_install() -> None:
            self._set_busy(True)
            self.progress_label.set_text("Installing update...")
            self._call_async(
                "POST",
                "/update/install",
                {"target": "latest", "allow_stop_streams": True},
                self._after_action,
            )

        self._confirm(
            "Install update",
            "AVream will stop camera/microphone if needed, install latest package, and restart daemon service. Continue?",
            do_install,
        )

    def _on_version_clicked(self, _btn) -> None:
        self._set_busy(True)
        self.progress_label.set_text("Checking for updates...")

        def done(result: dict) -> bool:
            self._set_busy(False)
            self.progress_label.set_text("")
            body = result.get("body", {}) if isinstance(result, dict) else {}
            if not isinstance(body, dict) or not body.get("ok"):
                err = body.get("error", {}) if isinstance(body, dict) else {}
                code = str(err.get("code", "E_UNKNOWN"))
                msg = str(err.get("message", "request failed"))
                if code == "E_DAEMON_UNREACHABLE":
                    self._set_daemon_lock(True, "AVream cannot reach daemon socket. Enable service and retry.")
                    return False
                self._show_error_dialog("Update check failed", f"{msg}\n\nError code: {code}")
                self._append_log(f"Update check failed: {code}: {msg}")
                self._refresh_status()
                return False

            data = body.get("data", {}) if isinstance(body, dict) else {}
            current = str(data.get("current_version", "unknown")) if isinstance(data, dict) else "unknown"
            latest = str(data.get("latest_version", "unknown")) if isinstance(data, dict) else "unknown"
            available = bool(data.get("update_available", False)) if isinstance(data, dict) else False
            release_url = data.get("latest_release_url") if isinstance(data, dict) else None
            if isinstance(release_url, str) and release_url:
                self._latest_release_url = release_url

            self._apply_version_indicator(current=current, latest=latest, available=available)

            dialog = Adw.MessageDialog.new(
                self,
                "Update available" if available else "No update",
                (
                    f"Current: {current}\nLatest: {latest}\n\n"
                    + ("A newer release is available." if available else "You are up to date.")
                ),
            )
            dialog.add_response("close", "Close")
            dialog.add_response("open_release", "Open Release")
            if available:
                dialog.add_response("install", "Install Update")
                dialog.set_response_appearance("install", Adw.ResponseAppearance.SUGGESTED)
            dialog.set_default_response("close")
            dialog.set_close_response("close")

            def on_response(dlg, resp_id: str) -> None:
                dlg.close()
                if resp_id == "open_release":
                    self._open_release_url(self._latest_release_url)
                elif resp_id == "install" and available:
                    self._run_update_install_with_confirm()

            dialog.connect("response", on_response)
            dialog.present()
            self._refresh_status()
            return False

        self._call_async("POST", "/update/check", {"force": True}, done)

    def _on_preview_window_toggled(self, switch, _pspec) -> None:
        if self._ignore_preview_toggle_event:
            return

        enabled = bool(switch.get_active())
        if self._video_running:
            self._ignore_preview_toggle_event = True
            switch.set_active(not enabled)
            self._ignore_preview_toggle_event = False
            self._show_info_dialog(
                "Cannot change while streaming",
                "Stop camera first, then change Preview window mode and start camera again.",
            )
            self._append_log("Preview window mode change blocked while camera is running.")
            return

        state = "on" if enabled else "off"
        self.preview_status_label.set_text(f"Preview window: {state}")
        self._append_log(f"Preview window mode set to {state}.")
        self._persist_current_ui_settings()
