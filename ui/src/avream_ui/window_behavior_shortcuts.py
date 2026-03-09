from __future__ import annotations

from gi.repository import Adw, Gdk, Gio, Gtk  # type: ignore[import-not-found]

from avream_ui.i18n import _

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


class WindowShortcutsMixin:
    _camera_toggle_shortcut: str

    def _setup_shortcuts(self) -> None:
        app = self.get_application()
        if app is None:
            return
        action = Gio.SimpleAction.new("toggle-camera", None)
        action.connect("activate", lambda _a, _p: self._on_stream_toggle(None))
        app.add_action(action)
        self._apply_shortcut_accel(self._camera_toggle_shortcut)

    def _apply_shortcut_accel(self, accel: str) -> None:
        app = self.get_application()
        if app is None:
            return
        app.set_accels_for_action("app.toggle-camera", [accel] if accel else [])

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
