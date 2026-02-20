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
        self._status_refresh_inflight = False
        self._status_refresh_pending = False
        self._devices_scan_inflight = False
        self._devices_scan_pending = False
        self._wifi_status_refresh_inflight = False
        self._wifi_status_refresh_pending = False
        self._wifi_status_refresh_source_id = 0
        self._startup_auto_connect_pending = True
        self._startup_auto_connect_attempted = False
        self._startup_auto_connect_completed = False

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        root.set_margin_top(16)
        root.set_margin_bottom(16)
        root.set_margin_start(16)
        root.set_margin_end(16)

        self.status_label = Gtk.Label(label="Status: unknown")
        self.status_label.set_xalign(0)
        self.status_label.set_wrap(True)

        self.progress_label = Gtk.Label(label="")
        self.progress_label.set_xalign(0)
        self.progress_label.add_css_class("dim-label")
        self.progress_label.set_wrap(True)

        self.stream_hint_label = Gtk.Label(label="Open Devices to choose a source, then start streaming here.")
        self.stream_hint_label.set_xalign(0)
        self.stream_hint_label.set_wrap(True)
        self.stream_hint_label.add_css_class("dim-label")
        self.stream_toggle_btn = Gtk.Button(label="Start Camera")
        self.phone_start_btn = self.stream_toggle_btn

        camera_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        camera_label = Gtk.Label(label="Camera lens")
        camera_label.set_xalign(0)
        camera_row.append(camera_label)
        self.camera_facing_dropdown = Gtk.DropDown.new_from_strings(["Front", "Back"])
        self.camera_facing_dropdown.set_selected(0)
        camera_row.append(self.camera_facing_dropdown)

        rotation_label = Gtk.Label(label="Rotation")
        rotation_label.set_xalign(0)
        camera_row.append(rotation_label)
        self.camera_rotation_dropdown = Gtk.DropDown.new_from_strings(["0°", "90°", "180°", "270°"])
        self.camera_rotation_dropdown.set_selected(0)
        camera_row.append(self.camera_rotation_dropdown)

        preview_label = Gtk.Label(label="Preview window")
        preview_label.set_xalign(0)
        camera_row.append(preview_label)
        self.preview_window_switch = Gtk.Switch()
        self.preview_window_switch.set_active(False)
        self.preview_window_switch.set_tooltip_text(
            "You can change preview window mode only when camera is stopped."
        )
        camera_row.append(self.preview_window_switch)

        self.preview_mode_hint_label = Gtk.Label(label="")
        self.preview_mode_hint_label.set_xalign(0)
        self.preview_mode_hint_label.add_css_class("dim-label")

        self.preview_status_label = Gtk.Label(label="Preview window: off (separate window)")
        self.preview_status_label.set_xalign(0)

        stream_controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        stream_controls.append(self.stream_toggle_btn)
        self.open_devices_btn = Gtk.Button(label="Open Devices")
        self.open_devices_btn.add_css_class("flat")
        stream_controls.append(self.open_devices_btn)

        stream_status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        stream_status_box.set_margin_top(10)
        stream_status_box.set_margin_bottom(10)
        stream_status_box.set_margin_start(12)
        stream_status_box.set_margin_end(12)
        stream_title = Gtk.Label(label="Stream")
        stream_title.set_xalign(0)
        stream_title.add_css_class("title-4")
        stream_status_box.append(stream_title)
        stream_status_box.append(self.status_label)
        stream_status_box.append(self.progress_label)
        stream_status_frame = Gtk.Frame()
        stream_status_frame.set_child(stream_status_box)

        stream_action_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        stream_action_box.set_margin_top(10)
        stream_action_box.set_margin_bottom(10)
        stream_action_box.set_margin_start(12)
        stream_action_box.set_margin_end(12)
        stream_action_box.append(self.stream_hint_label)
        self.stream_source_label = Gtk.Label(label="Active source: not selected")
        self.stream_source_label.set_xalign(0)
        self.stream_source_label.add_css_class("dim-label")
        stream_action_box.append(self.stream_source_label)
        stream_action_box.append(stream_controls)
        stream_action_frame = Gtk.Frame()
        stream_action_frame.set_child(stream_action_box)

        stream_settings_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        stream_settings_box.set_margin_top(10)
        stream_settings_box.set_margin_bottom(10)
        stream_settings_box.set_margin_start(12)
        stream_settings_box.set_margin_end(12)
        settings_title = Gtk.Label(label="Stream settings")
        settings_title.set_xalign(0)
        settings_title.add_css_class("heading")
        stream_settings_box.append(settings_title)
        stream_settings_box.append(camera_row)
        stream_settings_box.append(self.preview_status_label)
        stream_settings_box.append(self.preview_mode_hint_label)
        stream_settings_frame = Gtk.Frame()
        stream_settings_frame.set_child(stream_settings_box)

        stream_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        stream_page.append(stream_status_frame)
        stream_page.append(stream_action_frame)
        stream_page.append(stream_settings_frame)
        stream_page.set_vexpand(True)

        phone_buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.phone_scan_btn = Gtk.Button(label="Scan Phones")
        self.phone_connect_toggle_btn = Gtk.Button(label="Connect")
        # Aliases kept for existing mixins (_set_busy expects these attributes).
        self.phone_use_btn = self.phone_connect_toggle_btn
        self.phone_disconnect_btn = self.phone_connect_toggle_btn
        for btn in (self.phone_scan_btn, self.phone_connect_toggle_btn):
            phone_buttons.append(btn)

        mode_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        mode_label = Gtk.Label(label="Connection mode")
        mode_label.set_xalign(0)
        mode_row.append(mode_label)
        self.connection_mode_dropdown = Gtk.DropDown.new_from_strings(["USB", "Wi-Fi"])
        self.connection_mode_dropdown.set_selected(1)
        self.connection_mode_dropdown.set_sensitive(False)
        mode_row.append(self.connection_mode_dropdown)

        self.phone_list = Gtk.ListBox()
        self.phone_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        empty_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        empty_box.set_valign(Gtk.Align.CENTER)
        empty_box.set_halign(Gtk.Align.CENTER)
        empty_box.set_margin_top(24)
        empty_box.set_margin_bottom(24)
        empty_label = Gtk.Label(label="No phones detected yet.\nUse Scan Phones to refresh.")
        empty_label.set_justify(Gtk.Justification.CENTER)
        empty_label.add_css_class("dim-label")
        empty_box.append(empty_label)
        self.phone_list.set_placeholder(empty_box)
        phone_list_scroll = Gtk.ScrolledWindow()
        phone_list_scroll.set_vexpand(True)
        phone_list_scroll.set_child(self.phone_list)

        wifi_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        wifi_title = Gtk.Label(label="Manual Wi-Fi endpoint")
        wifi_title.set_xalign(0)
        wifi_box.append(wifi_title)
        self.phone_wifi_endpoint_entry = Gtk.Entry()
        self.phone_wifi_endpoint_entry.set_placeholder_text("IP or IP:PORT (e.g. 192.168.1.10)")
        wifi_box.append(self.phone_wifi_endpoint_entry)
        self.wifi_manual_help_label = Gtk.Label(
            label="In Wi-Fi mode, Connect uses this endpoint when no phone is selected in the list."
        )
        self.wifi_manual_help_label.set_xalign(0)
        self.wifi_manual_help_label.set_wrap(True)
        self.wifi_manual_help_label.add_css_class("dim-label")
        wifi_box.append(self.wifi_manual_help_label)
        self.wifi_saved_status_label = Gtk.Label(label="Endpoint status: not set")
        self.wifi_saved_status_label.set_xalign(0)
        self.wifi_saved_status_label.add_css_class("heading")
        wifi_box.append(self.wifi_saved_status_label)

        self.phone_status_label = Gtk.Label(label="No device selected. Scan and choose a phone.")
        self.phone_status_label.set_xalign(0)
        self.phone_status_label.set_wrap(True)

        selection_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        selection_box.set_margin_top(10)
        selection_box.set_margin_bottom(10)
        selection_box.set_margin_start(12)
        selection_box.set_margin_end(12)
        selection_title = Gtk.Label(label="Selection")
        selection_title.set_xalign(0)
        selection_title.add_css_class("heading")
        selection_box.append(selection_title)
        selection_box.append(phone_buttons)
        selection_box.append(self.phone_status_label)
        selection_frame = Gtk.Frame()
        selection_frame.set_child(selection_box)

        connection_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        connection_box.set_margin_top(10)
        connection_box.set_margin_bottom(10)
        connection_box.set_margin_start(12)
        connection_box.set_margin_end(12)
        connection_title = Gtk.Label(label="Connection")
        connection_title.set_xalign(0)
        connection_title.add_css_class("heading")
        connection_box.append(connection_title)
        connection_box.append(mode_row)
        connection_box.append(phone_list_scroll)
        connection_frame = Gtk.Frame()
        connection_frame.set_child(connection_box)

        wifi_frame = Gtk.Frame()
        wifi_frame.set_child(wifi_box)

        devices_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        devices_page.append(selection_frame)
        devices_page.append(connection_frame)
        devices_page.append(wifi_frame)
        devices_page.set_vexpand(True)

        self.passwordless_toggle_btn = Gtk.Button(label="Enable")

        self.ui_settings_reset_btn = Gtk.Button(label="Reset Saved")
        self.video_reset_btn = Gtk.Button(label="Reset Camera")
        self.video_reset_btn.add_css_class("destructive-action")

        advanced_page = Adw.PreferencesPage()

        security_group = Adw.PreferencesGroup(
            title="Security",
            description="Configure privileged helper access and authentication behavior.",
        )
        passwordless_row = Adw.ActionRow(
            title="Passwordless helper actions",
            subtitle="Status: unknown",
        )
        passwordless_buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        passwordless_buttons.append(self.passwordless_toggle_btn)
        passwordless_row.add_suffix(passwordless_buttons)
        passwordless_row.set_activatable(False)
        security_group.add(passwordless_row)
        self.passwordless_status_row = passwordless_row
        advanced_page.add(security_group)

        ui_group = Adw.PreferencesGroup(
            title="UI",
            description="Settings stored locally for the current user session.",
        )
        ui_settings_row = Adw.ActionRow(
            title="UI settings",
            subtitle="Auto-saved.",
        )
        ui_buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        ui_buttons.append(self.ui_settings_reset_btn)
        ui_settings_row.add_suffix(ui_buttons)
        ui_settings_row.set_activatable(False)
        ui_group.add(ui_settings_row)
        self.ui_settings_status_row = ui_settings_row
        advanced_page.add(ui_group)

        maintenance_group = Adw.PreferencesGroup(
            title="Maintenance",
            description="Actions for troubleshooting and recovering from device issues.",
        )
        reset_row = Adw.ActionRow(
            title="Reset camera device",
            subtitle="Reloads the virtual camera device. Use only if the stream is stuck.",
        )
        reset_row.add_suffix(self.video_reset_btn)
        reset_row.set_activatable(False)
        maintenance_group.add(reset_row)
        advanced_page.add(maintenance_group)

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

        advanced_page.set_vexpand(True)

        diagnostics_controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.refresh_btn = Gtk.Button(label="Refresh Status")
        self.copy_logs_btn = Gtk.Button(label="Copy Logs")
        self.clear_logs_btn = Gtk.Button(label="Clear Logs")
        diagnostics_controls.append(self.refresh_btn)
        diagnostics_controls.append(self.copy_logs_btn)
        diagnostics_controls.append(self.clear_logs_btn)

        self.log_view = Gtk.TextView()
        self.log_view.set_editable(False)
        self.log_view.set_monospace(True)
        log_scroll = Gtk.ScrolledWindow()
        log_scroll.set_vexpand(True)
        log_scroll.set_child(self.log_view)

        diagnostics_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        diagnostics_page.append(diagnostics_controls)
        diagnostics_page.append(log_scroll)
        diagnostics_page.set_vexpand(True)

        self.workspace_stack = Gtk.Stack()
        self.workspace_stack.add_titled(stream_page, "stream", "Stream")
        self.workspace_stack.add_titled(devices_page, "devices", "Devices")
        self.workspace_stack.add_titled(advanced_page, "advanced", "Advanced")
        self.workspace_stack.add_titled(diagnostics_page, "diagnostics", "Diagnostics")
        self.workspace_stack.set_vexpand(True)

        switcher = Gtk.StackSwitcher()
        switcher.set_stack(self.workspace_stack)
        switcher.set_halign(Gtk.Align.FILL)
        switcher.set_hexpand(True)
        root.append(switcher)
        root.append(self.workspace_stack)
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
        self.phone_connect_toggle_btn.connect("clicked", self._on_phone_connect_toggle)
        self.stream_toggle_btn.connect("clicked", self._on_stream_toggle)
        self.open_devices_btn.connect("clicked", lambda *_args: self.workspace_stack.set_visible_child_name("devices"))
        self.passwordless_toggle_btn.connect("clicked", self._on_passwordless_toggle)
        self.ui_settings_reset_btn.connect("clicked", self._on_ui_settings_reset)
        self.version_btn.connect("clicked", self._on_version_clicked)
        self.open_cli_readme_btn.connect("clicked", self._on_open_cli_readme)
        self.video_reset_btn.connect("clicked", self._on_video_reset)
        self.refresh_btn.connect("clicked", self._on_refresh)
        self.copy_logs_btn.connect("clicked", self._on_copy_logs)
        self.clear_logs_btn.connect("clicked", self._on_clear_logs)
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
        self._passwordless_enabled = False
        self._sync_stream_toggle_button()

        self._load_ui_settings()
        self._apply_loaded_ui_settings()

        self._refresh_status()
        self._refresh_passwordless_status()
        self._refresh_saved_wifi_endpoint_status()

        self.connect("close-request", self._on_close_request)
