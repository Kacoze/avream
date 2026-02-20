# AVream Installation and Upgrade

This page covers Debian/Ubuntu installation with one-liner, APT repository, and manual package paths.

## Recommended: one-liner installer

Install latest AVream:

```bash
curl -fsSL https://raw.githubusercontent.com/Kacoze/avream/main/scripts/install.sh | bash
```

Install specific version:

```bash
curl -fsSL https://raw.githubusercontent.com/Kacoze/avream/main/scripts/install.sh | AVREAM_VERSION=1.0.4 bash
```

The installer:
- Tries APT repository first (if available for your release).
- Falls back to GitHub Release `.deb` package.
- Enables/restarts `avreamd.service` for the current user session when possible.

## Manual APT repository setup

Use this when you want regular `apt upgrade` updates.

```bash
curl -fsSL https://raw.githubusercontent.com/Kacoze/avream/apt-repo/apt/avream-archive-keyring.gpg \
  | sudo tee /usr/share/keyrings/avream-archive-keyring.gpg >/dev/null
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/avream-archive-keyring.gpg] \
https://raw.githubusercontent.com/Kacoze/avream/apt-repo/apt stable main" \
  | sudo tee /etc/apt/sources.list.d/avream.list >/dev/null
sudo apt update
sudo apt install avream
```

## Manual package install

Monolithic package:

```bash
sudo apt install ./avream_<version>_amd64.deb
```

Split packages (advanced):

```bash
tar -xzf avream-deb-split_<version>_amd64.tar.gz
sudo apt install ./avream-daemon_<version>_amd64.deb \
  ./avream-ui_<version>_amd64.deb \
  ./avream-helper_<version>_amd64.deb
```

Or transitional meta package:

```bash
sudo apt install ./avream-meta_<version>_amd64.deb
```

## Upgrade

If installed from APT repository:

```bash
sudo apt update
sudo apt upgrade avream
```

If installed from local `.deb`:

```bash
sudo apt install ./avream_<new-version>_amd64.deb
```

## Uninstall

Use helper script:

```bash
curl -fsSL https://raw.githubusercontent.com/Kacoze/avream/main/scripts/uninstall.sh | bash
```

Or manually:

```bash
sudo apt remove avream avream-meta avream-daemon avream-ui avream-helper
sudo rm -f /etc/apt/sources.list.d/avream.list /usr/share/keyrings/avream-archive-keyring.gpg
```

Optional local cleanup:

```bash
rm -rf ~/.config/avream ~/.local/state/avream "$XDG_RUNTIME_DIR/avream"
```

## Verify installation

```bash
curl -fsSL https://raw.githubusercontent.com/Kacoze/avream/main/scripts/doctor.sh | bash
```

Or manual checks:

```bash
systemctl --user status avreamd.service
avream --help
avream-ui --help
```

If daemon is not reachable, see `docs/TROUBLESHOOTING.md`.
