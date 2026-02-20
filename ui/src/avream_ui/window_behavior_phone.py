from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
from typing import Any

from avream_ui.window_state import SelectedPhone

from gi.repository import Gtk  # type: ignore[import-not-found]


class WindowPhoneMixin:
    @staticmethod
    def _wifi_status_connected(status_text: str) -> bool:
        normalized = str(status_text or "").strip().lower()
        return normalized.startswith("endpoint status: connected")

    def _sync_phone_connect_toggle_button(self) -> None:
        mode = self._selected_connection_mode()
        endpoint = self.phone_wifi_endpoint_entry.get_text().strip()
        wifi_label = self.wifi_saved_status_label.get_text().strip()
        wifi_connected = self._wifi_status_connected(wifi_label)

        if mode == "wifi":
            if endpoint and wifi_connected:
                self.phone_connect_toggle_btn.set_label("Disconnect")
                self.phone_connect_toggle_btn.set_tooltip_text("Disconnect Wi-Fi endpoint from AVream session.")
            else:
                self.phone_connect_toggle_btn.set_label("Connect")
                self.phone_connect_toggle_btn.set_tooltip_text("Connect selected Wi-Fi device or manual endpoint.")
            return

        # USB mode: "connect" really means "use selected phone"; keep wording clear.
        if self._selected_phone:
            self.phone_connect_toggle_btn.set_label("Disconnect")
            self.phone_connect_toggle_btn.set_tooltip_text("Stop stream and disconnect selected phone from AVream session.")
        else:
            self.phone_connect_toggle_btn.set_label("Connect")
            self.phone_connect_toggle_btn.set_tooltip_text("Mark selected USB phone as active for streaming.")

    def _on_phone_connect_toggle(self, _btn) -> None:
        mode = self._selected_connection_mode()
        endpoint = self.phone_wifi_endpoint_entry.get_text().strip()
        wifi_label = self.wifi_saved_status_label.get_text().strip()
        wifi_connected = self._wifi_status_connected(wifi_label)

        if mode == "wifi":
            # Prefer disconnect when we know it's connected, or when user has an endpoint and wants to stop it.
            if endpoint and wifi_connected:
                self._on_phone_disconnect_selected(_btn)
                return
            self._on_phone_use_selected(_btn)
            return

        # USB mode: if a phone is selected, "Disconnect" is meaningful (stops stream first).
        if self._selected_phone:
            self._on_phone_disconnect_selected(_btn)
            return
        self._on_phone_use_selected(_btn)

    def _on_phone_scan(self, _btn) -> None:
        if self._devices_scan_inflight:
            self._devices_scan_pending = True
            self.progress_label.set_text("Scanning devices...")
            return

        self._devices_scan_inflight = True
        self.progress_label.set_text("Scanning devices...")

        def done(resp: dict) -> bool:
            self._devices_scan_inflight = False
            body = resp.get("body", {})
            if not body.get("ok"):
                self.progress_label.set_text("")
                self._after_action(resp)
                if self._devices_scan_pending:
                    self._devices_scan_pending = False
                    self._on_phone_scan(None)
                return False

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
            self._refresh_saved_wifi_endpoint_status()
            self._sync_phone_connect_toggle_button()
            if self._devices_scan_pending:
                self._devices_scan_pending = False
                self._on_phone_scan(None)
            return False

        self._call_async("GET", "/android/devices", None, done)

    def _populate_phone_list(
        self,
        devices: list[dict[str, Any]],
        recommended_id: str | None,
        available_transports: list[str],
    ) -> None:
        self._listbox_clear(self.phone_list)
        self._selected_phone = None
        self._apply_mode_from_available_transports(available_transports)
        self._sync_phone_connect_toggle_button()
        if not devices:
            self.phone_status_label.set_text("No phones detected. Connect USB phone and click Scan.")
            return
        self.phone_status_label.set_text("Select a phone to connect (USB or Wi-Fi).")

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
        else:
            self._restore_last_selected_device()

    def _on_phone_selected(self, _lb, row) -> None:
        if row is None:
            self._selected_phone = None
            if hasattr(self, "stream_source_label"):
                self.stream_source_label.set_text("Active source: not selected")
            self._sync_phone_connect_toggle_button()
            return
        phone = getattr(row, "_avream_phone", None)
        if not isinstance(phone, dict):
            self._selected_phone = None
            if hasattr(self, "stream_source_label"):
                self.stream_source_label.set_text("Active source: not selected")
            self._sync_phone_connect_toggle_button()
            return
        selected = SelectedPhone.from_payload(phone)
        if not selected.serial:
            self._selected_phone = None
            if hasattr(self, "stream_source_label"):
                self.stream_source_label.set_text("Active source: not selected")
            self._sync_phone_connect_toggle_button()
            return
        self._selected_phone = selected.as_dict()
        if hasattr(self, "stream_source_label"):
            mode = self._selected_connection_mode()
            self.stream_source_label.set_text(f"Active source: {selected.serial} ({mode})")

        self._apply_mode_from_selected_phone()
        self._sync_phone_connect_toggle_button()
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
            self.phone_status_label.set_text(f"Phone is ready ({t_label}). Click Connect.")

        self._persist_current_ui_settings()

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
                                    f"Wi-Fi device connected: {endpoint}. Open Stream tab to start camera."
                                )
                                self._persist_current_ui_settings()
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
                                        f"Wi-Fi ready: {endpoint2}. You can disconnect USB and start camera in Stream."
                                    )
                                    self._persist_current_ui_settings()
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
                                f"Wi-Fi ready: {endpoint}. You can disconnect USB and start camera in Stream."
                            )
                            self._persist_current_ui_settings()
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
                            f"Wi-Fi device connected: {endpoint}. Open Stream tab to start camera."
                        )
                        self._persist_current_ui_settings()
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
        self.phone_status_label.set_text("Phone selected and connected. Open Stream tab to start camera.")
        self._persist_current_ui_settings()

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
        payload["camera_rotation"] = self._selected_camera_rotation()
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

    def _selected_camera_rotation(self) -> int:
        selected = int(self.camera_rotation_dropdown.get_selected())
        if selected == 1:
            return 90
        if selected == 2:
            return 180
        if selected == 3:
            return 270
        return 0
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
            self._sync_phone_connect_toggle_button()
            return
        if transports == {"wifi"}:
            self.connection_mode_dropdown.set_selected(1)
            self.connection_mode_dropdown.set_sensitive(False)
            self._sync_phone_connect_toggle_button()
            return
        if transports == {"usb", "wifi"}:
            self.connection_mode_dropdown.set_selected(1)
        self.connection_mode_dropdown.set_sensitive(len(transports) > 1)
        self._sync_phone_connect_toggle_button()

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
        self._sync_phone_connect_toggle_button()
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
