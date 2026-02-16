# AVream Installation and Upgrade

This page covers installation paths for AVream on Debian/Ubuntu-based Linux.

## Recommended: monolithic package

Install one package containing daemon, UI, helper, and desktop assets:

```bash
sudo apt install ./avream_<version>_amd64.deb
```

Enable daemon service once per user:

```bash
mkdir -p ~/.config/avream
cp -n /usr/lib/systemd/user/avreamd.env ~/.config/avream/avreamd.env
systemctl --user daemon-reload
systemctl --user enable --now avreamd.service
```

## Advanced: split packages

Use this only when you need component-level installation.

```bash
sudo apt install ./avream-daemon_<version>_amd64.deb \
  ./avream-ui_<version>_amd64.deb \
  ./avream-helper_<version>_amd64.deb
```

Or use transitional meta package:

```bash
sudo apt install ./avream-meta_<version>_amd64.deb
```

## Upgrade

Upgrade with apt from local files:

```bash
sudo apt install ./avream_<new-version>_amd64.deb
```

For split packages, install matching versions together.

## Uninstall

Monolithic package:

```bash
sudo apt remove avream
```

Split packages:

```bash
sudo apt remove avream-meta avream-daemon avream-ui avream-helper
```

Optional local cleanup:

```bash
rm -rf ~/.config/avream ~/.local/state/avream "$XDG_RUNTIME_DIR/avream"
```

## Verify installation

```bash
systemctl --user status avreamd.service
avream --help
avream-ui --help
```

If daemon is not reachable, see `docs/TROUBLESHOOTING.md`.

On first GUI launch, AVream shows a daemon lock screen if service is not active. Use `Enable AVream Service` in GUI or run the manual commands above.
