# AVream Installation and Upgrade

This page covers all supported distribution channels: `APT/.deb`, `RPM`, `AUR`, `Nix`, `Snap`, `Flatpak`, and `PPA source`.

## Channel comparison

| Channel | Best for | Install updates | CI automation |
| --- | --- | --- | --- |
| APT / `.deb` | Debian/Ubuntu users | `apt upgrade` | `ci.yml`, `release.yml`, `nightly.yml` |
| RPM | Fedora/openSUSE users | `dnf upgrade` / `zypper update` | `ci.yml`, `release.yml`, `nightly.yml` |
| AUR | Arch users | `yay -Syu` / `paru -Syu` | `arch-validate.yml` |
| Nix | NixOS/Nix users | re-run `nix profile install` | `nix.yml` |
| Snap | Ubuntu Store flow | auto refresh + channel tracking | `snap.yml` |
| Flatpak | cross-distro desktop flow | `flatpak update` | `flatpak.yml` |
| PPA source | Ubuntu-native package pipeline | `apt upgrade` via PPA | `ppa.yml` |

## Recommended: one-liner installer

Install latest AVream:

```bash
curl -fsSL https://raw.githubusercontent.com/Kacoze/avream/main/scripts/install.sh | bash
```

Install specific GitHub release package version:

```bash
curl -fsSL https://raw.githubusercontent.com/Kacoze/avream/main/scripts/install.sh | AVREAM_VERSION=<version> bash
```

Force installer channel:

```bash
# Snap
curl -fsSL https://raw.githubusercontent.com/Kacoze/avream/main/scripts/install.sh | AVREAM_INSTALL_METHOD=snap bash

# Flatpak
curl -fsSL https://raw.githubusercontent.com/Kacoze/avream/main/scripts/install.sh | AVREAM_INSTALL_METHOD=flatpak bash
```

Installer behavior in `auto` mode:
- Debian/Ubuntu: APT repository first, fallback to `.deb` release package.
- Fedora/openSUSE: install from `.rpm` release package.
- Arch/Nix: points to native path (`AUR` / `flake`).

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

### Ubuntu PPA path (source package pipeline)

PPA publishing is automated by `.github/workflows/ppa.yml` (when secrets are configured).  
User-side install remains standard `apt` after adding your PPA:

```bash
sudo add-apt-repository ppa:<owner>/<ppa-name>
sudo apt update
sudo apt install avream
```

## Fedora / openSUSE

Install from release RPM:

```bash
# Fedora
sudo dnf install ./avream-<version>-1.x86_64.rpm

# openSUSE
sudo zypper --non-interactive --no-gpg-checks install ./avream-<version>-1.x86_64.rpm
```

## Arch Linux (AUR)

Use your AUR helper:

```bash
yay -S avream
# or
paru -S avream
```

Repository package sources are in `packaging/arch/`.

## Nix / NixOS

Install from flake:

```bash
nix profile install github:Kacoze/avream#avream
```

Run without installing profile:

```bash
nix run github:Kacoze/avream#avream-ui
```

## Snap (Ubuntu Software / Snap Store)

```bash
sudo snap install avream --classic
```

Track edge channel:

```bash
sudo snap refresh avream --channel=edge
```

## Flatpak (Flathub-style flow)

```bash
flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak install -y flathub io.avream.AVream
```

## Upgrade

- APT/PPA: `sudo apt update && sudo apt upgrade avream`
- DNF: `sudo dnf upgrade avream`
- zypper: `sudo zypper update avream`
- AUR: update via your helper (`yay -Syu` / `paru -Syu`)
- Nix: re-run `nix profile install github:Kacoze/avream#avream`
- Snap: `sudo snap refresh avream`
- Flatpak: `flatpak update io.avream.AVream`

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
