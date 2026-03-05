# Supported Platforms

## Tested environment

AVream is a personal project, built and manually tested on:

- **Ubuntu 24.04 (GNOME)** — the only environment receiving hands-on testing before each release

Architecture: amd64 / x86_64

## Other Linux distributions

AVream may work on other systemd-based Linux desktops. The CI pipeline builds and
smoke-tests packages on Ubuntu 22.04, Debian 12, Fedora 41 and openSUSE Tumbleweed,
but these are not manually verified on a real desktop.

Distributions that have a reasonable chance of working if dependencies are met:
- Debian 12+, Ubuntu 22.04+ and derivatives (Linux Mint, Pop!_OS, Zorin OS, …)
- Fedora 41+, openSUSE Leap/Tumbleweed
- Arch Linux (AUR path)
- NixOS (flake path)

There are no guarantees. Things may or may not work.

## Bug reports from other distributions

I build this for myself, but I am happy to look into issues reported from other systems.
If something doesn't work on your distribution, open an issue — I will do my best to help.

## Required system capabilities

- systemd user services
- polkit and desktop auth agent
- Linux virtual video support (`v4l2loopback`)

## Runtime tools (feature-dependent)

- `scrcpy` + `adb` (Android camera backend)
- `pulseaudio-utils` or `pw-loopback` (audio virtual mic path)

## Package model

- Recommended: monolithic `avream_<version>_amd64.deb`.
- Advanced: split packages (`avream-daemon`, `avream-ui`, `avream-helper`, `avream-meta`).
- RPM monolith: `avream-<version>-1.x86_64.rpm`.
- Arch: `PKGBUILD` in `packaging/arch/`.
- Nix: `flake.nix` package `.#avream`.
- Snap: `snap/snapcraft.yaml` (Snap Store path).
- Flatpak: `packaging/flatpak/io.avream.AVream.yml`.
- Ubuntu PPA source package pipeline: `debian/` + `.github/workflows/ppa.yml`.

## Out of scope

- Non-Linux platforms
- Non-amd64 builds (until explicitly added)
- Desktop stacks without a polkit auth agent
