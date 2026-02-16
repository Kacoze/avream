from __future__ import annotations

import sys


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
