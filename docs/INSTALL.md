---
description: Install AVream on Linux using the one-liner installer, APT, RPM, Arch, Nix, Snap, or Flatpak.
---

# AVream Installation and Upgrade

## Recommended: one-liner installer

Install latest AVream:

```bash
curl -fsSL https://raw.githubusercontent.com/Kacoze/avream/main/scripts/install.sh | bash
```

Install specific version:

```bash
curl -fsSL https://raw.githubusercontent.com/Kacoze/avream/main/scripts/install.sh | AVREAM_VERSION=<version> bash
```

Installer behavior in `auto` mode:
- Debian/Ubuntu: APT repository first, fallback to `.deb` release package.
- Fedora/openSUSE: install from `.rpm` release package.

## Debian / Ubuntu

### APT repository (recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/Kacoze/avream/apt-repo/apt/avream-archive-keyring.gpg \
  | sudo tee /usr/share/keyrings/avream-archive-keyring.gpg >/dev/null
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/avream-archive-keyring.gpg] \
https://raw.githubusercontent.com/Kacoze/avream/apt-repo/apt stable main" \
  | sudo tee /etc/apt/sources.list.d/avream.list >/dev/null
sudo apt update
sudo apt install avream
```

### Manual `.deb`

```bash
sudo apt install ./avream_<version>_amd64.deb
```

Split bundle (advanced):

```bash
tar -xzf avream-deb-split_<version>_amd64.tar.gz
sudo apt install ./avream-daemon_<version>_amd64.deb \
  ./avream-ui_<version>_amd64.deb \
  ./avream-helper_<version>_amd64.deb
```

## Fedora / openSUSE

Install from release RPM:

```bash
# Fedora
sudo dnf install ./avream-<version>-1.x86_64.rpm

# openSUSE
sudo zypper --non-interactive --no-gpg-checks install ./avream-<version>-1.x86_64.rpm
```

## Nix / NixOS

Install from flake:

```bash
nix profile install github:Kacoze/avream#avream
```

Run without installing profile:

```bash
nix run github:Kacoze/avream#avream-ui
```

## Upgrade

- APT: `sudo apt update && sudo apt upgrade avream`
- DNF: `sudo dnf upgrade avream`
- zypper: `sudo zypper update avream`
- Nix: re-run `nix profile install github:Kacoze/avream#avream`

## Uninstall

Use helper script:

```bash
curl -fsSL https://raw.githubusercontent.com/Kacoze/avream/main/scripts/uninstall.sh | bash
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
