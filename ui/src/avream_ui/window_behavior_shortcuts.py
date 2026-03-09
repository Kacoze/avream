from __future__ import annotations

import logging
import os

from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # type: ignore[import-not-found]

from avream_ui.i18n import _

_log = logging.getLogger(__name__)

# Keyvals that are pure modifiers (no binding makes sense alone)
_MODIFIER_KEYVALS: frozenset[int] = frozenset({
    getattr(Gdk, "KEY_Control_L", 0xFFE3),
    getattr(Gdk, "KEY_Control_R", 0xFFE4),
    getattr(Gdk, "KEY_Shift_L", 0xFFE1),
    getattr(Gdk, "KEY_Shift_R", 0xFFE2),
    getattr(Gdk, "KEY_Alt_L", 0xFFE9),
    getattr(Gdk, "KEY_Alt_R", 0xFFEA),
    getattr(Gdk, "KEY_Super_L", 0xFFEB),
    getattr(Gdk, "KEY_Super_R", 0xFFEC),
    getattr(Gdk, "KEY_Meta_L", 0xFFE7),
    getattr(Gdk, "KEY_Meta_R", 0xFFE8),
    getattr(Gdk, "KEY_Hyper_L", 0xFFED),
    getattr(Gdk, "KEY_Hyper_R", 0xFFEE),
    getattr(Gdk, "KEY_ISO_Level3_Shift", 0xFE03),
    getattr(Gdk, "KEY_Caps_Lock", 0xFFE5),
    getattr(Gdk, "KEY_Num_Lock", 0xFF7F),
})

_KEY_ESCAPE: int = getattr(Gdk, "KEY_Escape", 0xFF1B)

_PORTAL_BUS = "org.freedesktop.portal.Desktop"
_PORTAL_PATH = "/org/freedesktop/portal/desktop"
_PORTAL_IFACE = "org.freedesktop.portal.GlobalShortcuts"
_SHORTCUT_ID = "toggle-camera"


def _useful_modifier_mask() -> int:
    """Returns an integer mask of shift/control/alt/super modifier bits."""
    result = 0
    for name in ("SHIFT_MASK", "CONTROL_MASK", "ALT_MASK", "SUPER_MASK"):
        val = getattr(Gdk.ModifierType, name, None)
        if val is not None:
            try:
                result |= int(val)
            except TypeError:
                pass
    return result


_USEFUL_MODS: int = _useful_modifier_mask()


class _PortalShortcutSession:
    """Global shortcut via the XDG GlobalShortcuts portal (Wayland/GNOME 43+).

    Falls back silently when the portal is unavailable.
    """

    def __init__(self, callback, on_shortcuts_changed=None) -> None:
        self._callback = callback
        self._on_change_cb = on_shortcuts_changed
        self._portal: Gio.DBusProxy | None = None
        self._bus: Gio.DBusConnection | None = None
        self._session_path: str | None = None
        self._tok = 0
        self._response_sub: int = 0

    def _next_token(self) -> str:
        self._tok += 1
        return f"avream{self._tok}"

    def start(self, accel: str) -> None:
        try:
            self._bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            self._portal = Gio.DBusProxy.new_sync(
                self._bus,
                Gio.DBusProxyFlags.DO_NOT_AUTO_START,
                None,
                _PORTAL_BUS,
                _PORTAL_PATH,
                _PORTAL_IFACE,
                None,
            )
        except Exception as e:
            _log.debug("GlobalShortcuts portal: proxy creation failed: %s", e)
            return

        handle_token = self._next_token()
        session_token = self._next_token()

        sender = self._bus.get_unique_name().lstrip(":").replace(".", "_")
        request_path = f"/org/freedesktop/portal/desktop/request/{sender}/{handle_token}"

        self._response_sub = self._bus.signal_subscribe(
            _PORTAL_BUS,
            "org.freedesktop.portal.Request",
            "Response",
            request_path,
            None,
            Gio.DBusSignalFlags.NONE,
            lambda _c, _s, _p, _i, _sig, params: self._on_create_response(params, accel),
        )

        try:
            self._portal.call(
                "CreateSession",
                GLib.Variant(
                    "(a{sv})",
                    (
                        {
                            "handle_token": GLib.Variant("s", handle_token),
                            "session_handle_token": GLib.Variant("s", session_token),
                        },
                    ),
                ),
                Gio.DBusCallFlags.NONE,
                -1,
                None,
                lambda _src, _res: None,
            )
            _log.debug("GlobalShortcuts portal: CreateSession sent")
        except Exception as e:
            _log.debug("GlobalShortcuts portal: CreateSession failed: %s", e)
            self._bus.signal_unsubscribe(self._response_sub)

    def _on_create_response(self, params: GLib.Variant, accel: str) -> None:
        if self._bus:
            self._bus.signal_unsubscribe(self._response_sub)
        response = params[0]
        if int(response) != 0:
            _log.debug("GlobalShortcuts portal: CreateSession response error %d", int(response))
            return
        results = params[1].unpack()
        session_handle = results.get("session_handle")
        if not session_handle:
            _log.debug("GlobalShortcuts portal: CreateSession response missing session_handle")
            return
        self._session_path = str(session_handle)
        _log.debug("GlobalShortcuts portal: session created at %s", self._session_path)

        if self._bus:
            self._bus.signal_subscribe(
                _PORTAL_BUS,
                _PORTAL_IFACE,
                "Activated",
                self._session_path,
                None,
                Gio.DBusSignalFlags.NONE,
                self._on_activated,
            )
            self._bus.signal_subscribe(
                _PORTAL_BUS,
                _PORTAL_IFACE,
                "ShortcutsChanged",
                self._session_path,
                None,
                Gio.DBusSignalFlags.NONE,
                self._on_shortcuts_changed,
            )

        self._bind(accel)

    def _on_activated(
        self, _conn, _sender, _path, _iface, _signal, params: GLib.Variant
    ) -> None:
        unpacked = params.unpack()
        shortcut_id = unpacked[1]
        _log.debug("GlobalShortcuts portal: Activated shortcut_id=%r", shortcut_id)
        if shortcut_id == _SHORTCUT_ID:
            GLib.idle_add(self._callback)

    def _on_shortcuts_changed(
        self, _conn, _sender, _path, _iface, _signal, params: GLib.Variant
    ) -> None:
        shortcuts = params.unpack()[1]  # list of (id, options_dict)
        for sid, opts in shortcuts:
            if sid == _SHORTCUT_ID:
                trigger = opts.get("trigger-description", "")
                _log.debug("GlobalShortcuts portal: ShortcutsChanged trigger=%r", trigger)
                if trigger and self._on_change_cb:
                    GLib.idle_add(self._on_change_cb, trigger)
                break

    def _bind(self, accel: str) -> None:
        if not self._portal or not self._session_path:
            return
        handle_token = self._next_token()
        shortcut_trigger = GLib.Variant("s", accel if accel else "")
        try:
            self._portal.call(
                "BindShortcuts",
                GLib.Variant(
                    "(oa(sa{sv})sa{sv})",
                    (
                        self._session_path,
                        [
                            (
                                _SHORTCUT_ID,
                                {
                                    "description": GLib.Variant(
                                        "s", "Toggle AVream camera"
                                    ),
                                    "preferred-trigger": shortcut_trigger,
                                },
                            )
                        ],
                        "",
                        {"handle_token": GLib.Variant("s", handle_token)},
                    ),
                ),
                Gio.DBusCallFlags.NONE,
                -1,
                None,
                lambda _src, _res: None,
            )
            _log.debug("GlobalShortcuts portal: BindShortcuts sent accel=%r", accel)
        except Exception as e:
            _log.debug("GlobalShortcuts portal: BindShortcuts failed: %s", e)

    def update(self, accel: str) -> None:
        """Rebind after shortcut changes."""
        if self._session_path:
            self._bind(accel)


class _KeybinderShortcut:
    """Global shortcut via libkeybinder-3.0 (X11).

    Optional — silently skipped if gir1.2-keybinder-3.0 is not installed.
    """

    def __init__(self, callback) -> None:
        self._callback = callback
        self._accel = ""
        self._kb = None
        try:
            import gi
            gi.require_version("Keybinder", "3.0")
            from gi.repository import Keybinder  # type: ignore[import-not-found]
            Keybinder.init()
            self._kb = Keybinder
            _log.debug("Keybinder: initialized (X11 global shortcut)")
        except Exception as e:
            _log.debug("Keybinder: not available: %s", e)

    def start(self, accel: str) -> None:
        if not self._kb or not accel:
            return
        try:
            self._kb.bind(accel, lambda _a: self._callback())
            self._accel = accel
            _log.debug("Keybinder: bound %s", accel)
        except Exception as e:
            _log.debug("Keybinder: bind failed: %s", e)

    def update(self, accel: str) -> None:
        if not self._kb:
            return
        if self._accel:
            try:
                self._kb.unbind(self._accel)
            except Exception:
                pass
            self._accel = ""
        self.start(accel)


class WindowShortcutsMixin:
    _camera_toggle_shortcut: str
    _portal_session: _PortalShortcutSession | None = None
    _keybinder_shortcut: _KeybinderShortcut | None = None

    def _setup_shortcuts(self) -> None:
        app = self.get_application()
        if app is None:
            return
        action = Gio.SimpleAction.new("toggle-camera", None)
        action.connect("activate", lambda _a, _p: self._on_stream_toggle(None))
        app.add_action(action)
        self._apply_shortcut_accel(self._camera_toggle_shortcut)

        cb = lambda: self._on_stream_toggle(None)
        if os.environ.get("WAYLAND_DISPLAY"):
            self._portal_session = _PortalShortcutSession(
                cb, on_shortcuts_changed=self._on_portal_shortcuts_changed
            )
            self._portal_session.start(self._camera_toggle_shortcut)
            self._keybinder_shortcut = None
        else:
            self._portal_session = None
            self._keybinder_shortcut = _KeybinderShortcut(cb)
            self._keybinder_shortcut.start(self._camera_toggle_shortcut)

    def _apply_shortcut_accel(self, accel: str) -> None:
        app = self.get_application()
        if app is None:
            return
        app.set_accels_for_action("app.toggle-camera", [accel] if accel else [])
        if self._portal_session is not None:
            self._portal_session.update(accel)
        if self._keybinder_shortcut is not None:
            self._keybinder_shortcut.update(accel)

    def _on_portal_shortcuts_changed(self, trigger: str) -> None:
        if hasattr(self, "_shortcut_toggle_row"):
            self._shortcut_toggle_row.set_subtitle(trigger)

    def _shortcut_label(self, accel: str) -> str:
        if not accel:
            return _("Disabled")
        try:
            parsed = Gtk.accelerator_parse(accel)
            if isinstance(parsed, tuple) and len(parsed) == 3:
                ok, key, mods = parsed
            elif isinstance(parsed, tuple) and len(parsed) == 2:
                key, mods = parsed
                ok = bool(key)
            else:
                return accel
            if ok and key:
                return Gtk.accelerator_get_label(key, mods)
        except Exception:
            pass
        return accel

    def _on_shortcut_row_activated(self, _row) -> None:
        dialog = Adw.MessageDialog.new(
            self,
            _("Camera Toggle Shortcut"),
            _("Press a key combination to assign to camera toggle.\nPress Escape to cancel."),
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", lambda d, _r: d.close())

        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self._on_capture_key_pressed, dialog)
        dialog.add_controller(key_ctrl)

        dialog.present()

    def _on_capture_key_pressed(
        self,
        _ctrl,
        keyval: int,
        _keycode: int,
        state: Gdk.ModifierType,
        dialog,
    ) -> bool:
        if keyval in _MODIFIER_KEYVALS:
            return True

        clean = int(state) & _USEFUL_MODS
        if keyval == _KEY_ESCAPE and clean == 0:
            dialog.close()
            return True

        accel = Gtk.accelerator_name(keyval, Gdk.ModifierType(clean))
        if not accel:
            return True

        self._camera_toggle_shortcut = accel
        self._apply_shortcut_accel(accel)
        if hasattr(self, "_shortcut_toggle_row"):
            self._shortcut_toggle_row.set_subtitle(self._shortcut_label(accel))
        if callable(getattr(self, "_persist_current_ui_settings", None)):
            self._persist_current_ui_settings()
        dialog.close()
        return True

    def _on_shortcut_disable_clicked(self, _btn) -> None:
        self._camera_toggle_shortcut = ""
        self._apply_shortcut_accel("")
        if hasattr(self, "_shortcut_toggle_row"):
            self._shortcut_toggle_row.set_subtitle(self._shortcut_label(""))
        if callable(getattr(self, "_persist_current_ui_settings", None)):
            self._persist_current_ui_settings()
