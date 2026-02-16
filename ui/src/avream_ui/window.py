from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import threading
from typing import Any

from avream_ui.api_client import ApiClient

from gi.repository import Adw, GLib, Gtk  # type: ignore[import-not-found]


class AvreamWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.set_title("AVream")
        self.set_default_size(780, 560)

        header = Adw.HeaderBar()
        header.set_title_widget(Gtk.Label(label="AVream"))
        header.set_show_end_title_buttons(True)

        self.api = ApiClient()
        self._busy = False
        self._selected_phone: dict[str, Any] | None = None
        self._daemon_locked = False

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        root.set_margin_top(16)
        root.set_margin_bottom(16)
        root.set_margin_start(16)
        root.set_margin_end(16)

        self.status_label = Gtk.Label(label="Status: unknown")
        self.status_label.set_xalign(0)
        root.append(self.status_label)

        self.progress_label = Gtk.Label(label="")
        self.progress_label.set_xalign(0)
        root.append(self.progress_label)

        self.phone_status_label = Gtk.Label(label="Connect your Android phone via USB and enable USB debugging.")
        self.phone_status_label.set_xalign(0)
        self.phone_status_label.set_wrap(True)
        root.append(self.phone_status_label)

        phone_buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.phone_scan_btn = Gtk.Button(label="Scan Phones")
        self.phone_use_btn = Gtk.Button(label="Use Selected Phone")
        self.phone_disconnect_btn = Gtk.Button(label="Disconnect Selected")
        self.phone_start_btn = Gtk.Button(label="Start Camera")
        for btn in (self.phone_scan_btn, self.phone_use_btn, self.phone_disconnect_btn):
            phone_buttons.append(btn)
        root.append(phone_buttons)

        mode_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        mode_label = Gtk.Label(label="Connection mode:")
        mode_label.set_xalign(0)
        mode_row.append(mode_label)
        self.connection_mode_dropdown = Gtk.DropDown.new_from_strings(["USB", "Wi-Fi"])
        self.connection_mode_dropdown.set_selected(1)
        self.connection_mode_dropdown.set_sensitive(False)
        mode_row.append(self.connection_mode_dropdown)
        root.append(mode_row)

        camera_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        camera_label = Gtk.Label(label="Camera lens:")
        camera_label.set_xalign(0)
        camera_row.append(camera_label)
        self.camera_facing_dropdown = Gtk.DropDown.new_from_strings(["Front", "Back"])
        self.camera_facing_dropdown.set_selected(0)
        camera_row.append(self.camera_facing_dropdown)

        preview_label = Gtk.Label(label="Preview window:")
        preview_label.set_xalign(0)
        camera_row.append(preview_label)
        self.preview_window_switch = Gtk.Switch()
        self.preview_window_switch.set_active(False)
        self.preview_window_switch.set_tooltip_text(
            "You can change preview window mode only when camera is stopped."
        )
        camera_row.append(self.preview_window_switch)
        root.append(camera_row)

        self.preview_mode_hint_label = Gtk.Label(label="")
        self.preview_mode_hint_label.set_xalign(0)
        self.preview_mode_hint_label.add_css_class("dim-label")
        root.append(self.preview_mode_hint_label)

        self.phone_list = Gtk.ListBox()
        self.phone_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        phone_list_scroll = Gtk.ScrolledWindow()
        phone_list_scroll.set_vexpand(True)
        phone_list_scroll.set_child(self.phone_list)
        root.append(phone_list_scroll)

        wifi_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        wifi_title = Gtk.Label(label="Wi-Fi (optional)")
        wifi_title.set_xalign(0)
        wifi_box.append(wifi_title)
        self.phone_wifi_endpoint_entry = Gtk.Entry()
        self.phone_wifi_endpoint_entry.set_placeholder_text("IP or IP:PORT (e.g. 192.168.1.10)")
        wifi_box.append(self.phone_wifi_endpoint_entry)
        root.append(wifi_box)

        auth_expander = Gtk.Expander(label="Advanced (Passwordless auth)")
        auth_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        auth_btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.passwordless_status_btn = Gtk.Button(label="Check")
        self.passwordless_enable_btn = Gtk.Button(label="Enable")
        self.passwordless_disable_btn = Gtk.Button(label="Disable")
        auth_btn_row.append(self.passwordless_status_btn)
        auth_btn_row.append(self.passwordless_enable_btn)
        auth_btn_row.append(self.passwordless_disable_btn)
        auth_box.append(auth_btn_row)
        self.passwordless_status_label = Gtk.Label(label="Passwordless helper actions: unknown")
        self.passwordless_status_label.set_xalign(0)
        self.passwordless_status_label.set_wrap(True)
        auth_box.append(self.passwordless_status_label)
        auth_expander.set_child(auth_box)
        root.append(auth_expander)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        controls.append(self.phone_start_btn)
        self.video_stop_btn = Gtk.Button(label="Stop Camera")
        self.video_reset_btn = Gtk.Button(label="Reset Camera")
        self.refresh_btn = Gtk.Button(label="Refresh")
        for btn in (
            self.video_stop_btn,
            self.video_reset_btn,
            self.refresh_btn,
        ):
            controls.append(btn)
        root.append(controls)

        self.preview_status_label = Gtk.Label(label="Preview window: off (separate window)")
        self.preview_status_label.set_xalign(0)
        root.append(self.preview_status_label)

        self.log_view = Gtk.TextView()
        self.log_view.set_editable(False)
        self.log_view.set_monospace(True)
        log_scroll = Gtk.ScrolledWindow()
        log_scroll.set_vexpand(True)
        log_scroll.set_child(self.log_view)
        root.append(log_scroll)

        docs_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        docs_row.set_halign(Gtk.Align.END)
        self.open_cli_readme_btn = Gtk.Button(label="CLI help")
        self.open_cli_readme_btn.add_css_class("flat")
        self.open_cli_readme_btn.add_css_class("pill")
        self.open_cli_readme_btn.set_tooltip_text("Open AVream CLI quick reference")
        docs_row.append(self.open_cli_readme_btn)
        root.append(docs_row)

        self.lock_status_label = Gtk.Label(label="")
        self.lock_status_label.set_xalign(0)
        self.lock_status_label.set_wrap(True)

        self.enable_service_btn = Gtk.Button(label="Enable AVream Service")
        self.retry_service_btn = Gtk.Button(label="Retry")
        self.manual_service_btn = Gtk.Button(label="Show Manual Commands")

        lock_controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lock_controls.append(self.enable_service_btn)
        lock_controls.append(self.retry_service_btn)
        lock_controls.append(self.manual_service_btn)

        lock_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        lock_box.set_margin_top(24)
        lock_box.set_margin_bottom(24)
        lock_box.set_margin_start(24)
        lock_box.set_margin_end(24)
        lock_title = Gtk.Label(label="AVream daemon is not running")
        lock_title.set_xalign(0)
        lock_title.add_css_class("title-3")
        lock_box.append(lock_title)
        lock_box.append(self.lock_status_label)
        lock_box.append(lock_controls)

        self.main_stack = Gtk.Stack()
        self.main_stack.add_titled(root, "main", "Main")
        self.main_stack.add_titled(lock_box, "daemon-lock", "Daemon lock")

        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(header)
        toolbar.set_content(self.main_stack)
        self.set_content(toolbar)

        self.phone_scan_btn.connect("clicked", self._on_phone_scan)
        self.phone_use_btn.connect("clicked", self._on_phone_use_selected)
        self.phone_disconnect_btn.connect("clicked", self._on_phone_disconnect_selected)
        self.phone_start_btn.connect("clicked", self._on_phone_start)
        self.passwordless_status_btn.connect("clicked", self._on_passwordless_status)
        self.passwordless_enable_btn.connect("clicked", self._on_passwordless_enable)
        self.passwordless_disable_btn.connect("clicked", self._on_passwordless_disable)
        self.open_cli_readme_btn.connect("clicked", self._on_open_cli_readme)
        self.video_stop_btn.connect("clicked", self._on_video_stop)
        self.video_reset_btn.connect("clicked", self._on_video_reset)
        self.refresh_btn.connect("clicked", self._on_refresh)
        self.enable_service_btn.connect("clicked", self._on_enable_service)
        self.retry_service_btn.connect("clicked", self._on_retry_service)
        self.manual_service_btn.connect("clicked", self._on_show_manual_commands)
        self.phone_list.connect("row-selected", self._on_phone_selected)
        self.phone_list.connect("row-activated", self._on_phone_activated)
        self.preview_window_switch.connect("notify::active", self._on_preview_window_toggled)

        self._video_running = False
        self._ignore_preview_toggle_event = False

        self._refresh_status()
        self._refresh_passwordless_status()

        self.connect("close-request", self._on_close_request)

    def _append_log(self, text: str) -> None:
        ts = datetime.utcnow().strftime("%H:%M:%S")
        line = f"[{ts}] {text}\n"
        buf = self.log_view.get_buffer()
        start, end = buf.get_bounds()
        existing = buf.get_text(start, end, False)
        buf.set_text(f"{existing}{line}")

    def _on_close_request(self, _window) -> bool:
        return False

    def _show_error_dialog(self, title: str, message: str) -> None:
        dialog = Adw.MessageDialog.new(self, title, message)
        dialog.add_response("close", "Close")
        dialog.set_default_response("close")
        dialog.set_close_response("close")
        dialog.connect("response", lambda d, _r: d.close())
        dialog.present()

    def _show_info_dialog(self, title: str, message: str) -> None:
        dialog = Adw.MessageDialog.new(self, title, message)
        dialog.add_response("ok", "OK")
        dialog.set_default_response("ok")
        dialog.set_close_response("ok")
        dialog.connect("response", lambda d, _r: d.close())
        dialog.present()

    def _confirm(self, title: str, message: str, on_ok) -> None:
        dialog = Adw.MessageDialog.new(self, title, message)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("ok", "Proceed")
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def _on_resp(d, resp_id) -> None:
            d.close()
            if resp_id == "ok":
                on_ok()

        dialog.connect("response", _on_resp)
        dialog.present()

    def _call(self, method: str, path: str, payload: dict | None = None) -> dict:
        try:
            result = self.api.request_sync(method, path, payload)
            self._append_log(f"{method} {path} -> HTTP {result['status']}")
            return {
                "status": result.get("status"),
                "body": result.get("body"),
                "_meta": {"method": method, "path": path, "payload": payload or {}},
            }
        except Exception as exc:
            self._append_log(f"{method} {path} failed: {exc}")
            return {
                "status": 0,
                "body": {
                    "ok": False,
                    "error": {
                        "code": "E_DAEMON_UNREACHABLE",
                        "message": str(exc),
                        "details": {"socket_path": self.api.socket_path},
                    },
                },
                "_meta": {"method": method, "path": path, "payload": payload or {}},
            }

    def _call_async(self, method: str, path: str, payload: dict | None, on_done) -> None:
        def run() -> None:
            result = self._call(method, path, payload)
            GLib.idle_add(on_done, result)

        threading.Thread(target=run, daemon=True).start()

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy

        if self._daemon_locked:
            self.enable_service_btn.set_sensitive(not busy)
            self.retry_service_btn.set_sensitive(not busy)
            self.manual_service_btn.set_sensitive(True)
            return

        for btn in (
            self.phone_scan_btn,
            self.phone_use_btn,
            self.phone_disconnect_btn,
            self.phone_start_btn,
            self.passwordless_status_btn,
            self.passwordless_enable_btn,
            self.passwordless_disable_btn,
            self.open_cli_readme_btn,
            self.video_stop_btn,
            self.video_reset_btn,
            self.refresh_btn,
        ):
            btn.set_sensitive(not busy)
        self.camera_facing_dropdown.set_sensitive(not busy)
        self.preview_window_switch.set_sensitive((not busy) and (not self._video_running))

    def _after_action(self, result: dict) -> bool:
        body = result.get("body", {})
        if not body.get("ok"):
            err = body.get("error", {}) if isinstance(body, dict) else {}
            code = err.get("code", "E_UNKNOWN")
            msg = err.get("message", "request failed")
            details = err.get("details", {}) if isinstance(err, dict) else {}
            hint = details.get("hint") if isinstance(details, dict) else None
            composed = f"{code}: {msg}"
            extra = self._extract_error_extra(details)
            if extra:
                composed += f"\n{extra}"
            if hint:
                composed += f"\nHint: {hint}"
            self._append_log(f"Error: {composed}")
            if code == "E_DAEMON_UNREACHABLE":
                self._set_daemon_lock(
                    True,
                    "AVream cannot reach daemon socket. Enable service and retry.",
                )
            else:
                self._show_error_dialog("AVream request failed", composed)
        else:
            success = self._describe_success(result)
            if success:
                self._append_log(success)
        self._set_busy(False)
        self.progress_label.set_text("")
        self._refresh_status()
        return False

    def _extract_error_extra(self, details: dict[str, Any]) -> str:
        result = details.get("result") if isinstance(details, dict) else None
        if isinstance(result, dict):
            serial = result.get("serial")
            endpoint = result.get("endpoint")
            stderr = result.get("stderr")
            chunks: list[str] = []
            if isinstance(serial, str) and serial:
                chunks.append(f"Device: {serial}")
            if isinstance(endpoint, str) and endpoint:
                chunks.append(f"Endpoint: {endpoint}")
            if isinstance(stderr, str) and stderr.strip():
                chunks.append(f"Details: {stderr.strip()}")
            if chunks:
                return "\n".join(chunks)
        return ""

    def _describe_success(self, result: dict) -> str:
        meta = result.get("_meta", {}) if isinstance(result, dict) else {}
        path = meta.get("path") if isinstance(meta, dict) else ""
        body = result.get("body", {}) if isinstance(result, dict) else {}
        data = body.get("data", {}) if isinstance(body, dict) else {}

        if path == "/video/start":
            source = data.get("source", {}) if isinstance(data, dict) else {}
            serial = source.get("serial") if isinstance(source, dict) else None
            facing = source.get("camera_facing") if isinstance(source, dict) else None
            preview_window = source.get("preview_window") if isinstance(source, dict) else None
            audio = data.get("audio") if isinstance(data, dict) else None
            facing_label = None
            if isinstance(facing, str) and facing in {"front", "back"}:
                facing_label = facing
            if isinstance(serial, str) and serial:
                preview_part = ""
                if isinstance(preview_window, bool):
                    preview_part = ", preview window: on" if preview_window else ", preview window: off"
                audio_part = ""
                if isinstance(audio, dict):
                    if audio.get("state") == "RUNNING":
                        audio_part = ", mic: on"
                    elif audio.get("state") == "ERROR":
                        audio_part = ", mic: failed"
                if facing_label:
                    return f"Camera started (device: {serial}, lens: {facing_label}{preview_part}{audio_part})."
                return f"Camera started (device: {serial}{preview_part}{audio_part})."
            return "Camera started."

        if path == "/video/stop":
            audio = data.get("audio") if isinstance(data, dict) else None
            if isinstance(audio, dict) and audio.get("state") == "STOPPED":
                return "Camera stopped (mic stopped)."
            return "Camera stopped."

        if path == "/video/reset":
            return "Camera device reset completed."

        if path == "/audio/start":
            return "Microphone started."

        if path == "/audio/stop":
            return "Microphone stopped."

        if path == "/android/wifi/setup":
            endpoint = data.get("endpoint") if isinstance(data, dict) else None
            serial = data.get("serial") if isinstance(data, dict) else None
            conn = None
            result_obj = data.get("result") if isinstance(data, dict) else None
            if isinstance(result_obj, dict):
                conn = result_obj.get("connect")
            attempts = None
            if isinstance(conn, dict):
                attempt = conn.get("attempt")
                total = conn.get("attempts")
                if isinstance(attempt, int) and isinstance(total, int):
                    attempts = f" (attempt {attempt}/{total})"
            if isinstance(endpoint, str) and isinstance(serial, str):
                suffix = attempts or ""
                return f"Wi-Fi setup complete: {serial} -> {endpoint}{suffix}."
            return "Wi-Fi setup complete."

        if path == "/android/wifi/connect":
            endpoint = data.get("endpoint") if isinstance(data, dict) else None
            if isinstance(endpoint, str) and endpoint:
                return f"Wi-Fi connected: {endpoint}."
            return "Wi-Fi connected."

        if path == "/android/wifi/disconnect":
            endpoint = data.get("endpoint") if isinstance(data, dict) else None
            if isinstance(endpoint, str) and endpoint:
                return f"Wi-Fi disconnected: {endpoint}."
            return "Wi-Fi disconnected."

        return ""

    def _refresh_status(self) -> None:
        resp = self._call("GET", "/status")
        body = resp.get("body", {})
        if not body.get("ok"):
            err = body.get("error", {}) if isinstance(body, dict) else {}
            code = err.get("code", "E_UNKNOWN")
            msg = err.get("message", "unknown error")
            if code == "E_DAEMON_UNREACHABLE":
                self._set_daemon_lock(
                    True,
                    "AVream daemon service is not active for this user session.",
                )
                self.status_label.set_text("Status: daemon unavailable")
                return

            self._set_daemon_lock(False)
            self.status_label.set_text(f"Status error: {code}: {msg}")
            return

        self._set_daemon_lock(False)

        data = body.get("data", {}) if isinstance(body, dict) else {}
        runtime = data.get("runtime", {}) if isinstance(data, dict) else {}
        video_rt = runtime.get("video", {}) if isinstance(runtime, dict) else {}
        audio_rt = runtime.get("audio", {}) if isinstance(runtime, dict) else {}
        video_state = video_rt.get("state", "unknown") if isinstance(video_rt, dict) else "unknown"
        audio_state = audio_rt.get("state", "unknown") if isinstance(audio_rt, dict) else "unknown"
        self.status_label.set_text(f"Camera: {video_state} | Microphone: {audio_state}")
        self._video_running = video_state == "RUNNING"

        active_source = video_rt.get("active_source", {}) if isinstance(video_rt, dict) else {}
        preview_window = False
        if isinstance(active_source, dict):
            preview_window = bool(active_source.get("preview_window", False))

        if self._video_running:
            self.preview_window_switch.set_sensitive(False)
            self.preview_window_switch.set_tooltip_text(
                "Stop camera first to change preview window mode."
            )
            mode = "on" if preview_window else "off"
            self.preview_status_label.set_text(f"Preview window: {mode} (locked while camera is running)")
            self.preview_mode_hint_label.set_text("Stop camera first to change preview window mode.")
        else:
            self.preview_window_switch.set_sensitive(not self._busy)
            self.preview_window_switch.set_tooltip_text(
                "Toggle to show or hide separate AVream Preview window on next camera start."
            )
            mode = "on" if self.preview_window_switch.get_active() else "off"
            self.preview_status_label.set_text(f"Preview window: {mode}")
            self.preview_mode_hint_label.set_text("")

    def _set_daemon_lock(self, locked: bool, reason: str | None = None) -> None:
        self._daemon_locked = locked
        if locked:
            message = reason or "AVream daemon is required before using camera and phone controls."
            self.lock_status_label.set_text(
                f"{message}\n\n"
                "Click 'Enable AVream Service' for one-time setup, or use manual commands."
            )
            self.main_stack.set_visible_child_name("daemon-lock")
            return

        self.main_stack.set_visible_child_name("main")

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

    def _on_phone_scan(self, _btn) -> None:
        self.progress_label.set_text("Scanning devices...")
        resp = self._call("GET", "/android/devices")
        body = resp.get("body", {})
        if not body.get("ok"):
            self._after_action(resp)
            return

        data = body.get("data", {}) if isinstance(body, dict) else {}
        devices = data.get("devices", []) if isinstance(data, dict) else []
        recommended_id = data.get("recommended_id") if isinstance(data, dict) else None
        available_transports = data.get("available_transports") if isinstance(data, dict) else []
        if not isinstance(devices, list):
            devices = []
        if not isinstance(available_transports, list):
            available_transports = []
        self._populate_phone_list(
            devices,
            recommended_id if isinstance(recommended_id, str) else None,
            [str(t) for t in available_transports],
        )
        self.progress_label.set_text("")
        self._append_log(f"Device scan complete: {len(devices)} device(s) found.")

    def _populate_phone_list(
        self,
        devices: list[dict[str, Any]],
        recommended_id: str | None,
        available_transports: list[str],
    ) -> None:
        self._listbox_clear(self.phone_list)
        self._selected_phone = None
        self._apply_mode_from_available_transports(available_transports)
        if not devices:
            self.phone_status_label.set_text("No phones detected. Plug USB cable, enable USB debugging, and unlock phone.")
            return
        self.phone_status_label.set_text("Select your phone (USB or Wi-Fi). If unauthorized, unlock and accept the USB debugging prompt.")

        selected_row: Gtk.ListBoxRow | None = None
        for d in devices:
            if not isinstance(d, dict):
                continue
            serial = d.get("serial")
            state = d.get("state")
            transport = d.get("transport")
            transports_raw = d.get("transports")
            transports: list[Any] = transports_raw if isinstance(transports_raw, list) else []
            serials_raw = d.get("serials")
            serials: dict[str, Any] = serials_raw if isinstance(serials_raw, dict) else {}
            device_id = d.get("id")
            wifi_candidate_endpoint = d.get("wifi_candidate_endpoint")
            wifi_candidate_ip = d.get("wifi_candidate_ip")
            if not isinstance(serial, str):
                continue
            state_s = str(state or "")
            transport_s = str(transport or "")
            transports_s = ",".join(str(t) for t in transports) if transports else transport_s

            usb_serial = str(serials.get("usb", "")) if isinstance(serials, dict) else ""
            wifi_endpoint = str(serials.get("wifi", "")) if isinstance(serials, dict) else ""
            device_id_str = str(device_id or "")
            wifi_candidate = str(wifi_candidate_endpoint or "")
            wifi_ip = str(wifi_candidate_ip or "")

            if usb_serial and wifi_endpoint:
                label = f"ID: {device_id_str}" if device_id_str else serial
                subtitle = f"{state_s} ({transports_s}) | USB: {usb_serial} | Wi-Fi: {wifi_endpoint}"
            elif usb_serial and wifi_candidate:
                label = f"ID: {device_id_str}" if device_id_str else usb_serial
                subtitle = (
                    f"{state_s} ({transports_s}) | USB: {usb_serial} | "
                    f"Wi-Fi candidate: {wifi_candidate}"
                )
            elif usb_serial:
                label = usb_serial
                subtitle = f"{state_s} ({transports_s})"
            elif wifi_endpoint:
                label = f"ID: {device_id_str}" if device_id_str else wifi_endpoint
                subtitle = f"{state_s} ({transports_s}) | Wi-Fi: {wifi_endpoint}"
            else:
                label = serial
                subtitle = f"{state_s} ({transports_s})" if transports_s else state_s

            if wifi_candidate and not wifi_endpoint and wifi_ip:
                subtitle += f" (IP: {wifi_ip})"

            row = Gtk.ListBoxRow()
            row.set_child(self._listbox_row_child_label_text(label, subtitle))
            setattr(
                row,
                "_avream_phone",
                {
                    "id": str(device_id or ""),
                    "serial": serial,
                    "state": state_s,
                    "transport": transport_s,
                    "transports": [str(t) for t in transports],
                    "serials": {str(k): str(v) for k, v in serials.items()},
                    "wifi_candidate_endpoint": wifi_candidate,
                    "wifi_candidate_ip": wifi_ip,
                },
            )
            self.phone_list.append(row)

            if recommended_id and str(device_id or "") == recommended_id:
                selected_row = row

        if selected_row is not None:
            self.phone_list.select_row(selected_row)

    def _on_phone_selected(self, _lb, row) -> None:
        if row is None:
            self._selected_phone = None
            return
        phone = getattr(row, "_avream_phone", None)
        if not isinstance(phone, dict):
            self._selected_phone = None
            return
        serial = phone.get("serial")
        if not isinstance(serial, str) or not serial:
            self._selected_phone = None
            return
        self._selected_phone = {
            "id": str(phone.get("id", "")),
            "serial": serial,
            "state": str(phone.get("state", "")),
            "transport": str(phone.get("transport", "")),
            "transports": list(phone.get("transports", [])) if isinstance(phone.get("transports"), list) else [],
            "serials": dict(phone.get("serials", {})) if isinstance(phone.get("serials"), dict) else {},
            "wifi_candidate_endpoint": str(phone.get("wifi_candidate_endpoint", "")),
            "wifi_candidate_ip": str(phone.get("wifi_candidate_ip", "")),
        }

        self._apply_mode_from_selected_phone()
        selected = self._selected_phone
        if not isinstance(selected, dict):
            return

        if selected.get("state") == "unauthorized":
            self.phone_status_label.set_text("Phone is unauthorized. Unlock phone and accept the USB debugging prompt.")
        elif selected.get("state") != "device":
            self.phone_status_label.set_text(f"Phone state: {selected.get('state')}. Try reconnecting USB.")
        else:
            transports = selected.get("transports")
            if isinstance(transports, list) and transports:
                t_label = ",".join(str(t) for t in transports)
            else:
                t_label = str(selected.get("transport") or "unknown")
            self.phone_status_label.set_text(f"Phone is ready ({t_label}). Click 'Start Camera' or choose another row.")

    def _on_phone_activated(self, _lb, row) -> None:
        # Double-click/Enter on row = immediate use for smoother USB/Wi-Fi switching.
        self._on_phone_selected(_lb, row)
        self._on_phone_use_selected(None)

    def _on_phone_use_selected(self, _btn) -> None:
        mode = self._selected_connection_mode()

        if not self._selected_phone:
            if mode == "wifi":
                endpoint = self.phone_wifi_endpoint_entry.get_text().strip()
                if endpoint:
                    self._set_busy(True)
                    self.progress_label.set_text("Connecting Wi-Fi endpoint...")

                    def done_manual_wifi(resp: dict) -> bool:
                        self._after_action(resp)
                        self._on_phone_scan(None)
                        return False

                    self._call_async("POST", "/android/wifi/connect", {"endpoint": endpoint}, done_manual_wifi)
                    return
            self._show_error_dialog("No phone selected", "Scan phones and select a device first.")
            return
        if self._selected_phone.get("state") != "device":
            self._show_error_dialog("Phone not ready", "Unlock phone and ensure it shows as 'device' in the list.")
            return

        serial = str(self._selected_phone.get("serial", ""))
        serials = self._selected_serials()
        usb_serial = serials.get("usb")
        wifi_serial = serials.get("wifi")
        wifi_candidate = str(self._selected_phone.get("wifi_candidate_endpoint", ""))

        if mode == "wifi":
            self._set_busy(True)
            if usb_serial and not wifi_serial:
                if wifi_candidate:
                    self.progress_label.set_text("Connecting Wi-Fi candidate endpoint...")

                    def done_candidate(resp: dict) -> bool:
                        body = resp.get("body", {}) if isinstance(resp, dict) else {}
                        if isinstance(body, dict) and body.get("ok"):
                            data = body.get("data", {}) if isinstance(body, dict) else {}
                            endpoint = data.get("endpoint") if isinstance(data, dict) else None
                            if isinstance(endpoint, str) and endpoint:
                                self.phone_wifi_endpoint_entry.set_text(endpoint)
                                self.phone_status_label.set_text(
                                    f"Wi-Fi phone selected: {endpoint}. Click 'Start Camera' to begin streaming."
                                )
                            self._after_action(resp)
                            self._on_phone_scan(None)
                            return False

                        # Candidate failed; fallback to full setup over USB.
                        self.progress_label.set_text("Candidate failed, setting up Wi-Fi from USB...")

                        def done_usb_wifi_fallback(resp2: dict) -> bool:
                            body2 = resp2.get("body", {}) if isinstance(resp2, dict) else {}
                            if isinstance(body2, dict) and body2.get("ok"):
                                data2 = body2.get("data", {}) if isinstance(body2, dict) else {}
                                endpoint2 = data2.get("endpoint") if isinstance(data2, dict) else None
                                if isinstance(endpoint2, str) and endpoint2:
                                    self.phone_wifi_endpoint_entry.set_text(endpoint2)
                                    self.phone_status_label.set_text(
                                        f"Wi-Fi ready: {endpoint2}. You can disconnect USB and start camera."
                                    )
                            self._after_action(resp2)
                            self._on_phone_scan(None)
                            return False

                        self._call_async(
                            "POST",
                            "/android/wifi/setup",
                            {"serial": usb_serial, "port": 5555},
                            done_usb_wifi_fallback,
                        )
                        return False

                    self._call_async("POST", "/android/wifi/connect", {"endpoint": wifi_candidate}, done_candidate)
                    return

                self.progress_label.set_text("Setting up Wi-Fi from selected USB phone...")

                def done_usb_wifi(resp: dict) -> bool:
                    body = resp.get("body", {}) if isinstance(resp, dict) else {}
                    if isinstance(body, dict) and body.get("ok"):
                        data = body.get("data", {}) if isinstance(body, dict) else {}
                        endpoint = data.get("endpoint") if isinstance(data, dict) else None
                        if isinstance(endpoint, str) and endpoint:
                            self.phone_wifi_endpoint_entry.set_text(endpoint)
                            self.phone_status_label.set_text(
                                f"Wi-Fi ready: {endpoint}. You can disconnect USB and start camera."
                            )
                    self._after_action(resp)
                    self._on_phone_scan(None)
                    return False

                self._call_async("POST", "/android/wifi/setup", {"serial": usb_serial, "port": 5555}, done_usb_wifi)
                return

            self.progress_label.set_text("Selecting Wi-Fi phone and reconnecting endpoint...")

            def done(resp: dict) -> bool:
                body = resp.get("body", {}) if isinstance(resp, dict) else {}
                if isinstance(body, dict) and body.get("ok"):
                    data = body.get("data", {}) if isinstance(body, dict) else {}
                    endpoint = data.get("endpoint") if isinstance(data, dict) else None
                    if isinstance(endpoint, str) and endpoint:
                        self.phone_wifi_endpoint_entry.set_text(endpoint)
                        self.phone_status_label.set_text(
                            f"Wi-Fi phone selected: {endpoint}. Click 'Start Camera' to begin streaming."
                        )
                self._after_action(resp)
                return False

            target_endpoint = wifi_serial or serial
            self._call_async("POST", "/android/wifi/connect", {"endpoint": target_endpoint}, done)
            return

        if not usb_serial:
            self._show_error_dialog(
                "USB mode selected",
                "Selected phone is Wi-Fi. Either switch connection mode to Wi-Fi or select a USB device.",
            )
            return
        self.phone_status_label.set_text("Phone selected. Click 'Start Camera' to begin streaming.")

    def _on_phone_start(self, _btn) -> None:
        self._set_busy(True)
        self.progress_label.set_text("Starting phone camera...")
        payload: dict[str, Any] = {}
        if self._selected_phone:
            serials = self._selected_serials()
            mode = self._selected_connection_mode()
            chosen = serials.get(mode) or self._selected_phone.get("serial")
            if isinstance(chosen, str) and chosen:
                payload["serial"] = chosen
        payload["camera_facing"] = self._selected_camera_facing()
        payload["preview_window"] = bool(self.preview_window_switch.get_active())
        self._call_async("POST", "/video/start", payload, self._after_action)

    def _on_phone_disconnect_selected(self, _btn) -> None:
        if not self._selected_phone:
            endpoint = self.phone_wifi_endpoint_entry.get_text().strip()
            if endpoint:
                self._set_busy(True)
                self.progress_label.set_text("Disconnecting Wi-Fi endpoint...")

                def done_manual_disc(resp_wifi: dict) -> bool:
                    self._after_action(resp_wifi)
                    self._on_phone_scan(None)
                    return False

                self._call_async("POST", "/android/wifi/disconnect", {"endpoint": endpoint}, done_manual_disc)
                return
            self._show_error_dialog("No phone selected", "Scan phones and select a device first.")
            return

        serial = str(self._selected_phone.get("serial", ""))
        serials = self._selected_serials()
        transport = self._selected_connection_mode()

        self._set_busy(True)
        self.progress_label.set_text("Disconnecting selected phone...")

        def done_video_stop(resp: dict) -> bool:
            # Always try to stop camera first for both USB and Wi-Fi flows.
            _ = resp
            wifi_endpoint = serials.get("wifi") or (serial if ":" in serial else "")
            if transport == "wifi" and wifi_endpoint:
                def done_wifi_disc(resp_wifi: dict) -> bool:
                    self._after_action(resp_wifi)
                    self._on_phone_scan(None)
                    return False

                self._call_async("POST", "/android/wifi/disconnect", {"endpoint": wifi_endpoint}, done_wifi_disc)
                return False

            self._set_busy(False)
            self.progress_label.set_text("")
            self.phone_status_label.set_text("Phone disconnected from AVream session.")
            self._append_log("Selected USB phone disconnected from AVream session.")
            self._refresh_status()
            return False

        self._call_async("POST", "/video/stop", {}, done_video_stop)

    def _selected_connection_mode(self) -> str:
        selected = int(self.connection_mode_dropdown.get_selected())
        return "wifi" if selected == 1 else "usb"

    def _selected_camera_facing(self) -> str:
        selected = int(self.camera_facing_dropdown.get_selected())
        return "back" if selected == 1 else "front"

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

    def _selected_serials(self) -> dict[str, str]:
        if not self._selected_phone:
            return {}
        serials = self._selected_phone.get("serials")
        if not isinstance(serials, dict):
            return {}
        return {str(k): str(v) for k, v in serials.items() if isinstance(v, str) and v}

    def _apply_mode_from_available_transports(self, available_transports: list[str]) -> None:
        transports = {t for t in available_transports if t in {"usb", "wifi"}}
        # Keep Wi-Fi selectable when only USB devices are listed, because Scan may
        # expose Wi-Fi candidate endpoint discoverable from USB.
        if transports == {"usb"}:
            self.connection_mode_dropdown.set_selected(1)
            self.connection_mode_dropdown.set_sensitive(True)
            return
        if transports == {"wifi"}:
            self.connection_mode_dropdown.set_selected(1)
            self.connection_mode_dropdown.set_sensitive(False)
            return
        if transports == {"usb", "wifi"}:
            self.connection_mode_dropdown.set_selected(1)
        self.connection_mode_dropdown.set_sensitive(len(transports) > 1)

    def _apply_mode_from_selected_phone(self) -> None:
        if not self._selected_phone:
            return
        transports = self._selected_phone.get("transports")
        if not isinstance(transports, list):
            return
        available = {str(t) for t in transports if str(t) in {"usb", "wifi"}}
        if available == {"usb"}:
            self.connection_mode_dropdown.set_selected(1)
            self.connection_mode_dropdown.set_sensitive(True)
        elif available == {"wifi"}:
            self.connection_mode_dropdown.set_selected(1)
            self.connection_mode_dropdown.set_sensitive(False)
        elif available == {"usb", "wifi"}:
            self.connection_mode_dropdown.set_selected(1)
            self.connection_mode_dropdown.set_sensitive(True)

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
        def run() -> None:
            try:
                proc = subprocess.run(command, capture_output=True, text=True, check=False)
                result = {
                    "ok": proc.returncode == 0,
                    "returncode": proc.returncode,
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                    "command": command,
                }
            except Exception as exc:
                result = {
                    "ok": False,
                    "returncode": -1,
                    "stdout": "",
                    "stderr": str(exc),
                    "command": command,
                }
            GLib.idle_add(on_done, result)

        threading.Thread(target=run, daemon=True).start()

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
            status_resp = self._call("GET", "/status")
            status_body = status_resp.get("body", {})
            runner = "unknown"
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

    def _listbox_clear(self, lb: Gtk.ListBox) -> None:
        row = lb.get_first_child()
        while row is not None:
            nxt = row.get_next_sibling()
            lb.remove(row)
            row = nxt

    def _listbox_row_child_label_text(self, label: str, subtitle: str) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_margin_start(6)
        box.set_margin_end(6)
        box.append(Gtk.Label(label=label, xalign=0))
        if subtitle:
            sub = Gtk.Label(label=subtitle, xalign=0)
            sub.add_css_class("dim-label")
            box.append(sub)
        return box
