from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from gi.repository import Adw  # type: ignore[import-not-found]


class WindowSettingsMixin:
    def _append_log(self, text: str) -> None:
        ts = datetime.utcnow().strftime("%H:%M:%S")
        line = f"[{ts}] {text}\n"
        buf = self.log_view.get_buffer()
        end_iter = buf.get_end_iter()
        buf.insert(end_iter, line)

    def _on_close_request(self, _window) -> bool:
        return False

    def _ui_settings_path(self) -> Path:
        cfg_home = os.getenv("XDG_CONFIG_HOME")
        base = Path(cfg_home) if cfg_home else (Path.home() / ".config")
        return base / "avream" / "ui-settings.json"

    def _load_ui_settings(self) -> None:
        self._saved_ui_settings = {}
        try:
            if not self._settings_path.exists():
                return
            payload = json.loads(self._settings_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                self._saved_ui_settings = payload
        except Exception as exc:
            self._append_log(f"UI settings load failed: {exc}")

    def _save_ui_settings(self) -> None:
        try:
            self._settings_path.parent.mkdir(parents=True, exist_ok=True)
            self._settings_path.write_text(
                json.dumps(self._saved_ui_settings, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            if hasattr(self, "ui_settings_status_label") and not self._ignore_settings_events:
                ts = datetime.utcnow().strftime("%H:%M:%S")
                self.ui_settings_status_label.set_text(f"UI settings saved at {ts}.")
        except Exception as exc:
            self._append_log(f"UI settings save failed: {exc}")
            if hasattr(self, "ui_settings_status_label"):
                self.ui_settings_status_label.set_text(f"UI settings save failed: {exc}")

    def _apply_default_ui_settings(self) -> None:
        self._ignore_settings_events = True
        try:
            self.connection_mode_dropdown.set_selected(1)
            self.camera_facing_dropdown.set_selected(0)
            self.camera_rotation_dropdown.set_selected(0)
            self.preview_window_switch.set_active(False)
            self.phone_wifi_endpoint_entry.set_text("")
            self._selected_phone = None
        finally:
            self._ignore_settings_events = False

    def _apply_loaded_ui_settings(self) -> None:
        self._ignore_settings_events = True
        try:
            mode = self._saved_ui_settings.get("connection_mode")
            if mode == "usb":
                self.connection_mode_dropdown.set_selected(0)
            elif mode == "wifi":
                self.connection_mode_dropdown.set_selected(1)

            facing = self._saved_ui_settings.get("camera_facing")
            if facing == "back":
                self.camera_facing_dropdown.set_selected(1)
            else:
                self.camera_facing_dropdown.set_selected(0)

            rotation = self._saved_ui_settings.get("camera_rotation")
            rotation_to_idx = {0: 0, 90: 1, 180: 2, 270: 3}
            if isinstance(rotation, int) and rotation in rotation_to_idx:
                self.camera_rotation_dropdown.set_selected(rotation_to_idx[rotation])
            else:
                self.camera_rotation_dropdown.set_selected(0)

            preview = self._saved_ui_settings.get("preview_window")
            if isinstance(preview, bool):
                self.preview_window_switch.set_active(preview)

            endpoint = self._saved_ui_settings.get("wifi_endpoint")
            if isinstance(endpoint, str) and endpoint.strip():
                self.phone_wifi_endpoint_entry.set_text(endpoint.strip())
        finally:
            self._ignore_settings_events = False

    def _persist_current_ui_settings(self) -> None:
        if self._ignore_settings_events:
            return
        self._saved_ui_settings["schema_version"] = 1
        self._saved_ui_settings["connection_mode"] = self._selected_connection_mode()
        self._saved_ui_settings["camera_facing"] = self._selected_camera_facing()
        self._saved_ui_settings["camera_rotation"] = self._selected_camera_rotation()
        self._saved_ui_settings["preview_window"] = bool(self.preview_window_switch.get_active())

        endpoint = self.phone_wifi_endpoint_entry.get_text().strip()
        if endpoint:
            self._saved_ui_settings["wifi_endpoint"] = endpoint
        else:
            self._saved_ui_settings.pop("wifi_endpoint", None)

        if isinstance(self._selected_phone, dict):
            device_id = self._selected_phone.get("id")
            if isinstance(device_id, str) and device_id:
                self._saved_ui_settings["last_device_id"] = device_id
            serials = self._selected_serials()
            usb = serials.get("usb")
            wifi = serials.get("wifi")
            if usb:
                self._saved_ui_settings["last_serial_usb"] = usb
            if wifi:
                self._saved_ui_settings["last_serial_wifi"] = wifi
            cand = self._selected_phone.get("wifi_candidate_endpoint")
            if isinstance(cand, str) and cand:
                self._saved_ui_settings["last_wifi_candidate_endpoint"] = cand
            ip = self._selected_phone.get("wifi_candidate_ip")
            if isinstance(ip, str) and ip:
                self._saved_ui_settings["last_wifi_candidate_ip"] = ip

        self._save_ui_settings()

    def _on_ui_setting_changed(self, *_args) -> None:
        self._persist_current_ui_settings()

    def _on_wifi_endpoint_changed(self, *_args) -> None:
        self._refresh_saved_wifi_endpoint_status()

    @staticmethod
    def _normalize_wifi_endpoint(endpoint: str) -> str:
        value = endpoint.strip()
        if not value:
            return ""
        if ":" in value:
            return value
        return f"{value}:5555"

    def _refresh_saved_wifi_endpoint_status(self) -> None:
        endpoint_raw = self.phone_wifi_endpoint_entry.get_text().strip()
        endpoint = self._normalize_wifi_endpoint(endpoint_raw)
        if not endpoint:
            self.wifi_saved_status_label.set_text("Saved Wi-Fi endpoint: not set")
            return

        def done(resp: dict) -> bool:
            body = resp.get("body", {}) if isinstance(resp, dict) else {}
            if not isinstance(body, dict) or not body.get("ok"):
                self.wifi_saved_status_label.set_text(f"✗ {endpoint} (status unknown: daemon/device scan unavailable)")
                return False

            data = body.get("data", {}) if isinstance(body, dict) else {}
            devices = data.get("devices", []) if isinstance(data, dict) else []
            if not isinstance(devices, list):
                devices = []

            matched_state = None
            for dev in devices:
                if not isinstance(dev, dict):
                    continue
                state = str(dev.get("state", "unknown"))
                serials = dev.get("serials") if isinstance(dev.get("serials"), dict) else {}
                wifi = str(serials.get("wifi", "")) if isinstance(serials, dict) else ""
                cand = str(dev.get("wifi_candidate_endpoint", ""))
                candidates = {
                    self._normalize_wifi_endpoint(wifi),
                    self._normalize_wifi_endpoint(cand),
                    wifi.strip(),
                    cand.strip(),
                }
                if endpoint in candidates or endpoint_raw in candidates:
                    matched_state = state
                    break

            if matched_state == "device":
                self.wifi_saved_status_label.set_text(f"✓ {endpoint} (connected)")
                return False
            if isinstance(matched_state, str):
                self.wifi_saved_status_label.set_text(f"✗ {endpoint} (state: {matched_state})")
                return False
            self.wifi_saved_status_label.set_text(f"✗ {endpoint} (not found)")
            return False

        self._call_async("GET", "/android/devices", None, done)

    def _on_ui_settings_save(self, _btn) -> None:
        self._persist_current_ui_settings()
        self._append_log("UI settings saved.")

    def _on_ui_settings_reset(self, _btn) -> None:
        def do_reset() -> None:
            self._saved_ui_settings = {}
            try:
                if self._settings_path.exists():
                    self._settings_path.unlink()
            except Exception as exc:
                self._append_log(f"UI settings reset failed: {exc}")
                self.ui_settings_status_label.set_text(f"UI settings reset failed: {exc}")
                return

            self._apply_default_ui_settings()
            self.ui_settings_status_label.set_text("Saved UI settings were reset to defaults.")
            self._append_log("UI settings reset to defaults.")

        self._confirm(
            "Reset saved UI settings",
            "This removes saved UI settings and restores defaults. Continue?",
            do_reset,
        )

    def _restore_last_selected_device(self) -> None:
        target_id = str(self._saved_ui_settings.get("last_device_id", "")).strip()
        target_usb = str(self._saved_ui_settings.get("last_serial_usb", "")).strip()
        target_wifi = str(self._saved_ui_settings.get("last_serial_wifi", "")).strip()
        target_candidate = str(self._saved_ui_settings.get("last_wifi_candidate_endpoint", "")).strip()

        if not any((target_id, target_usb, target_wifi, target_candidate)):
            return

        row = self.phone_list.get_first_child()
        while row is not None:
            phone = getattr(row, "_avream_phone", None)
            if isinstance(phone, dict):
                phone_id = str(phone.get("id", ""))
                serials = phone.get("serials") if isinstance(phone.get("serials"), dict) else {}
                usb = str(serials.get("usb", "")) if isinstance(serials, dict) else ""
                wifi = str(serials.get("wifi", "")) if isinstance(serials, dict) else ""
                cand = str(phone.get("wifi_candidate_endpoint", ""))
                if (
                    (target_id and phone_id and phone_id == target_id)
                    or (target_usb and usb and usb == target_usb)
                    or (target_wifi and wifi and wifi == target_wifi)
                    or (target_candidate and cand and cand == target_candidate)
                ):
                    self.phone_list.select_row(row)
                    return
            row = row.get_next_sibling()

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
