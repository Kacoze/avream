from __future__ import annotations

from typing import Any

from gi.repository import Gtk  # type: ignore[import-not-found]

try:
    from avreamd import __version__ as AVREAM_VERSION
except Exception:
    AVREAM_VERSION = "unknown"


class WindowCoreMixin:
    def _call(self, method: str, path: str, payload: dict | None = None) -> dict:
        return self.services.call(method, path, payload)

    def _call_async(self, method: str, path: str, payload: dict | None, on_done) -> None:
        self.services.call_async(method, path, payload, on_done)

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
            self.ui_settings_save_btn,
            self.ui_settings_reset_btn,
            self.version_btn,
            self.open_cli_readme_btn,
            self.video_stop_btn,
            self.video_reset_btn,
            self.refresh_btn,
        ):
            btn.set_sensitive(not busy)
        self.camera_facing_dropdown.set_sensitive(not busy)
        self.camera_rotation_dropdown.set_sensitive((not busy) and (not self._video_running))
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
        self._refresh_saved_wifi_endpoint_status()
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
            rotation = source.get("camera_rotation") if isinstance(source, dict) else None
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
                    rotation_part = ""
                    if isinstance(rotation, int):
                        rotation_part = f", rotation: {rotation}°"
                    return f"Camera started (device: {serial}, lens: {facing_label}{rotation_part}{preview_part}{audio_part})."
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

        if path == "/update/check":
            available = bool(data.get("update_available", False)) if isinstance(data, dict) else False
            current = data.get("current_version") if isinstance(data, dict) else None
            latest = data.get("latest_version") if isinstance(data, dict) else None
            if available:
                return f"Update available: {current} -> {latest}."
            return "Already up to date."

        if path == "/update/install":
            if isinstance(data, dict) and bool(data.get("already_up_to_date", False)):
                return "Already up to date."
            target = data.get("target_version") if isinstance(data, dict) else None
            if isinstance(target, str) and target:
                return f"Update installed to {target}. Daemon restart scheduled."
            return "Update installed. Daemon restart scheduled."

        return ""

    def _refresh_status(self) -> None:
        def done(resp: dict) -> bool:
            self._apply_status_response(resp)
            return False

        self._call_async("GET", "/status", None, done)

    def _apply_status_response(self, resp: dict) -> None:
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
        update_rt = data.get("update_runtime", {}) if isinstance(data, dict) else {}
        video_state = video_rt.get("state", "unknown") if isinstance(video_rt, dict) else "unknown"
        audio_state = audio_rt.get("state", "unknown") if isinstance(audio_rt, dict) else "unknown"
        self.status_label.set_text(f"Camera: {video_state} | Microphone: {audio_state}")
        self._video_running = video_state == "RUNNING"

        if isinstance(update_rt, dict):
            current = str(update_rt.get("current_version", "unknown"))
            latest = str(update_rt.get("latest_version", "unknown"))
            available = bool(update_rt.get("update_available", False))
            latest_release_url = update_rt.get("latest_release_url")
            if isinstance(latest_release_url, str) and latest_release_url:
                self._latest_release_url = latest_release_url
            self._apply_version_indicator(current=current, latest=latest, available=available)
        else:
            self._apply_version_indicator(current=AVREAM_VERSION, latest=None, available=False)

        active_source = video_rt.get("active_source", {}) if isinstance(video_rt, dict) else {}
        preview_window = False
        active_rotation = None
        if isinstance(active_source, dict):
            preview_window = bool(active_source.get("preview_window", False))
            rotation_val = active_source.get("camera_rotation")
            if isinstance(rotation_val, int):
                active_rotation = rotation_val

        if active_rotation in {0, 90, 180, 270}:
            idx = {0: 0, 90: 1, 180: 2, 270: 3}[active_rotation]
            self.camera_rotation_dropdown.set_selected(idx)

        if self._video_running:
            self.preview_window_switch.set_sensitive(False)
            self.camera_rotation_dropdown.set_sensitive(False)
            self.preview_window_switch.set_tooltip_text(
                "Stop camera first to change preview window mode."
            )
            self.camera_rotation_dropdown.set_tooltip_text(
                "Stop camera first to change rotation."
            )
            mode = "on" if preview_window else "off"
            self.preview_status_label.set_text(f"Preview window: {mode} (locked while camera is running)")
            self.preview_mode_hint_label.set_text("Stop camera first to change preview window mode and rotation.")
        else:
            self.preview_window_switch.set_sensitive(not self._busy)
            self.camera_rotation_dropdown.set_sensitive(not self._busy)
            self.preview_window_switch.set_tooltip_text(
                "Toggle to show or hide separate AVream Preview window on next camera start."
            )
            self.camera_rotation_dropdown.set_tooltip_text(
                "Select camera rotation for next camera start."
            )
            mode = "on" if self.preview_window_switch.get_active() else "off"
            self.preview_status_label.set_text(f"Preview window: {mode}")
            self.preview_mode_hint_label.set_text("")
