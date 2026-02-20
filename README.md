# AVream - Android Phone as Webcam and Microphone for Linux

[![Release](https://img.shields.io/github/v/release/kacoze/avream?sort=semver)](https://github.com/Kacoze/avream/releases/latest)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Linux-orange.svg)](docs/SUPPORTED_PLATFORMS.md)
[![CI](https://github.com/Kacoze/avream/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Kacoze/avream/actions/workflows/ci.yml)

AVream turns your Android phone into a Linux virtual camera and microphone for real meetings and recordings.

If you are looking for an Android phone as webcam on Linux, Android as microphone on Linux, or a reliable Linux virtual camera bridge for Zoom, Google Meet, and OBS, AVream is built for exactly that workflow.

Official website: https://kacoze.github.io/avream/

Website and documentation are generated from Markdown files in `docs/`.

## Why AVream

- No dedicated app required on the phone.
- Phone-first UX: scan phone, select device, start camera.
- USB and Wi-Fi modes with practical reconnect flow.
- Works as standard Linux devices: `AVream Camera` and `AVream Mic`.
- Includes both GUI (`avream-ui`) and CLI (`avream`).
- Security model based on polkit helper actions (no `sudo` in GUI controls).

## Works With

- Google Meet
- Zoom
- OBS Studio
- Other apps that support Linux V4L2 camera and Pulse/PipeWire microphone devices

## Quickstart (One-liner)

Install latest AVream with automatic service setup:

```bash
curl -fsSL https://raw.githubusercontent.com/Kacoze/avream/main/scripts/install.sh | bash
```

Install a specific release:

```bash
curl -fsSL https://raw.githubusercontent.com/Kacoze/avream/main/scripts/install.sh | AVREAM_VERSION=1.0.4 bash
```

Then launch:

```bash
avream-ui
```

If phone is not detected, open `Devices`, click `Scan Phones`, connect your phone via USB, unlock it, and accept USB debugging.

## CLI Quickstart

```bash
avream status
avream devices
avream start --mode wifi --lens front
avream camera stop
```

See `docs/CLI_README.md` for full command reference.

## Updates

- GUI: click version indicator in bottom-left to check updates and open update modal.
- CLI:

```bash
avream update status
avream update check --force
avream update install --allow-stop-streams
```

Update install verifies checksums from release assets before installing.

When an update is available, version indicator turns red and shows `current -> latest`.

## Install Options

- Recommended: one-liner installer (`scripts/install.sh`).
- APT repository (when enabled for releases): install with `apt install avream`.
- Manual monolithic package: `avream_<version>_amd64.deb`.
- Advanced Debian split bundle: `avream-deb-split_<version>_amd64.tar.gz` (contains `avream-daemon`, `avream-ui`, `avream-helper`, `avream-meta`).

Full install, upgrade, and uninstall guide: `docs/INSTALL.md`.

## Feature Snapshot

| Capability | AVream |
| --- | --- |
| Android phone webcam on Linux | Yes |
| Android phone microphone on Linux | Yes |
| USB and Wi-Fi workflows | Yes |
| GUI and CLI control | Yes |
| User daemon + structured API | Yes |
| No phone-side companion app required | Yes |

## Documentation

- User guide: `docs/USER_GUIDE.md`
- Installation and upgrade: `docs/INSTALL.md`
- CLI reference: `docs/CLI_README.md`
- Troubleshooting: `docs/TROUBLESHOOTING.md`
- FAQ: `docs/FAQ.md`
- Supported platforms: `docs/SUPPORTED_PLATFORMS.md`
- API contract: `docs/API_V1.md`

Release and security references:

- `docs/RELEASE_CHECKLIST.md`
- `docs/RELEASE_TEMPLATE.md`
- `docs/RC_DRILL.md`
- `docs/SECURITY_DECISIONS.md`

## Architecture

- `avreamd`: user daemon exposing JSON API over UNIX socket.
- `avream-ui`: GTK4/libadwaita desktop application.
- `avream-helper`: privileged helper for selected system actions via polkit.
- Modular services:
  - `VideoManager` now delegates process supervision, reconnect logic, and V4L2 reset to dedicated helpers, so the API-facing class stays lean (`src/avreamd/managers/video_manager.py`).
  - `UpdateManager` orchestrates reusable components that fetch releases, download assets, verify checksums, install updates, and schedule daemon restarts (`src/avreamd/managers/update/`).
  - Audio routing/backends live behind `AudioManager`, which now composes `PipeWireAudioBackend`, `SndAloopAudioBackend`, and a router that moves `scrcpy` output into the virtual sink (`src/avreamd/managers/audio/`).
  - CLI integrations reuse the new `CommandRunner` to capture stdout/stderr consistently (`src/avreamd/integrations/command_runner.py`).
- UI behavior is organized into mixins (`window_behavior_*.py`), so `ui/src/avream_ui/window.py` only wires widgets and delegates actions.

## Known Limits

- PC audio output to phone speaker is not in stable baseline.
- Preview runs as a separate `scrcpy` window, not embedded in GTK content.

## For Developers

Build local Debian packages:

```bash
bash scripts/build-deb.sh
bash scripts/build-deb-split.sh
```

Run local docs site (Markdown source of truth):

```bash
pip install mkdocs mkdocs-material
mkdocs serve
```

Build static docs site:

```bash
mkdocs build --strict
```

Release docs copied to `dist/` are generated by:

```bash
bash scripts/generate-dist-docs.sh
```

Installer and diagnostics helpers:

```bash
bash scripts/install.sh
bash scripts/doctor.sh
bash scripts/uninstall.sh
```
