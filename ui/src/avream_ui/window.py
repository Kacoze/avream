from __future__ import annotations

from typing import Any

from avream_ui.api_client import ApiClient
from avream_ui.window_behavior import WindowBehaviorMixin
from avream_ui.window_services import WindowServices

from gi.repository import Adw, Gtk  # type: ignore[import-not-found]

try:
    from avreamd import __version__ as AVREAM_VERSION
except Exception:
    AVREAM_VERSION = "unknown"


class AvreamWindow(WindowBehaviorMixin, Adw.ApplicationWindow):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.set_title("AVream")
        self.set_default_size(780, 560)

        header = Adw.HeaderBar()
        header.set_title_widget(Gtk.Label(label="AVream"))
        header.set_show_end_title_buttons(True)

        self.api = ApiClient()
        self.services = WindowServices(api=self.api, logger=self._append_log)
        self._busy = False
        self._selected_phone: dict[str, Any] | None = None
        self._daemon_locked = False
        self._ignore_settings_events = False
        self._saved_ui_settings: dict[str, Any] = {}
        self._settings_path = self._ui_settings_path()

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

        rotation_label = Gtk.Label(label="Rotation:")
        rotation_label.set_xalign(0)
        camera_row.append(rotation_label)
        self.camera_rotation_dropdown = Gtk.DropDown.new_from_strings(["0°", "90°", "180°", "270°"])
        self.camera_rotation_dropdown.set_selected(0)
        camera_row.append(self.camera_rotation_dropdown)

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
        self.wifi_saved_status_label = Gtk.Label(label="Saved Wi-Fi endpoint: not set")
        self.wifi_saved_status_label.set_xalign(0)
        self.wifi_saved_status_label.add_css_class("dim-label")
        wifi_box.append(self.wifi_saved_status_label)
        root.append(wifi_box)

        advanced_expander = Gtk.Expander(label="Advanced")
        advanced_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        auth_section_label = Gtk.Label(label="Passwordless auth")
        auth_section_label.set_xalign(0)
        auth_section_label.add_css_class("heading")
        advanced_box.append(auth_section_label)

        auth_btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.passwordless_status_btn = Gtk.Button(label="Check")
        self.passwordless_enable_btn = Gtk.Button(label="Enable")
        self.passwordless_disable_btn = Gtk.Button(label="Disable")
        auth_btn_row.append(self.passwordless_status_btn)
        auth_btn_row.append(self.passwordless_enable_btn)
        auth_btn_row.append(self.passwordless_disable_btn)
        advanced_box.append(auth_btn_row)
        self.passwordless_status_label = Gtk.Label(label="Passwordless helper actions: unknown")
        self.passwordless_status_label.set_xalign(0)
        self.passwordless_status_label.set_wrap(True)
        advanced_box.append(self.passwordless_status_label)

        advanced_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        settings_section_label = Gtk.Label(label="UI settings")
        settings_section_label.set_xalign(0)
        settings_section_label.add_css_class("heading")
        advanced_box.append(settings_section_label)

        settings_buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.ui_settings_save_btn = Gtk.Button(label="Save Settings")
        self.ui_settings_reset_btn = Gtk.Button(label="Reset Saved")
        settings_buttons.append(self.ui_settings_save_btn)
        settings_buttons.append(self.ui_settings_reset_btn)
        advanced_box.append(settings_buttons)
        self.ui_settings_status_label = Gtk.Label(label="UI settings are auto-saved.")
        self.ui_settings_status_label.set_xalign(0)
        self.ui_settings_status_label.set_wrap(True)
        advanced_box.append(self.ui_settings_status_label)

        advanced_expander.set_child(advanced_box)
        root.append(advanced_expander)

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
        docs_row.set_halign(Gtk.Align.FILL)
        docs_row.set_hexpand(True)
        self.version_btn = Gtk.Button(label=AVREAM_VERSION)
        self.version_btn.add_css_class("flat")
        self.version_btn.set_halign(Gtk.Align.START)
        self.version_btn.set_tooltip_text("Click to check for updates")
        docs_row.append(self.version_btn)
        docs_spacer = Gtk.Box()
        docs_spacer.set_hexpand(True)
        docs_row.append(docs_spacer)
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
        self.ui_settings_save_btn.connect("clicked", self._on_ui_settings_save)
        self.ui_settings_reset_btn.connect("clicked", self._on_ui_settings_reset)
        self.version_btn.connect("clicked", self._on_version_clicked)
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
        self.connection_mode_dropdown.connect("notify::selected", self._on_ui_setting_changed)
        self.camera_facing_dropdown.connect("notify::selected", self._on_ui_setting_changed)
        self.camera_rotation_dropdown.connect("notify::selected", self._on_ui_setting_changed)
        self.phone_wifi_endpoint_entry.connect("changed", self._on_ui_setting_changed)
        self.phone_wifi_endpoint_entry.connect("changed", self._on_wifi_endpoint_changed)

        self._video_running = False
        self._latest_release_url = "https://github.com/Kacoze/avream/releases/latest"
        self._ignore_preview_toggle_event = False

        self._load_ui_settings()
        self._apply_loaded_ui_settings()

        self._refresh_status()
        self._refresh_passwordless_status()
        self._refresh_saved_wifi_endpoint_status()

        self.connect("close-request", self._on_close_request)
