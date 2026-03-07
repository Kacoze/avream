from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _load_saved_language() -> str | None:
    config_home = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    settings_path = Path(config_home) / "avream" / "ui-settings.json"
    try:
        return json.loads(settings_path.read_text()).get("language")
    except Exception:
        return None


def main() -> int:
    try:
        import gi

        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw, Gtk
    except Exception as exc:
        print("AVream UI requires GTK4 + libadwaita Python bindings.", file=sys.stderr)
        print(f"Details: {exc}", file=sys.stderr)
        return 1

    saved_lang = _load_saved_language()
    from avream_ui.i18n import setup as _i18n_setup
    _i18n_setup(saved_lang)
    if saved_lang == "ar":
        from gi.repository import Gtk
        Gtk.Widget.set_default_direction(Gtk.TextDirection.RTL)

    from avream_ui.window import AvreamWindow

    class App(Adw.Application):
        def __init__(self) -> None:
            super().__init__(application_id="io.avream.AVream")

        def do_activate(self) -> None:  # type: ignore[override]
            win = self.props.active_window
            if win is None:
                win = AvreamWindow(application=self)
            win.present()

    app = App()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
