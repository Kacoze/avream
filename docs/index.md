# AVream

Turn your Android phone into a Linux virtual camera and microphone for real meetings and recordings.

[![Release](https://img.shields.io/github/v/release/kacoze/avream?sort=semver)](https://github.com/Kacoze/avream/releases/latest)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/Kacoze/avream/blob/main/LICENSE)
[![Platform](https://img.shields.io/badge/platform-Linux-orange.svg)](SUPPORTED_PLATFORMS.md)
[![CI](https://github.com/Kacoze/avream/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Kacoze/avream/actions/workflows/ci.yml)

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

## Quickstart (Recommended)

1. Download the latest monolithic package from Releases and install it:

```bash
sudo apt install ./avream_<version>_amd64.deb
```

2. Launch AVream GUI:

```bash
avream-ui
```

3. On first launch, if daemon lock screen appears, click `Enable AVream Service`.
4. Connect phone with USB, unlock it, and accept USB debugging authorization.
5. Click `Scan Phones`, select your device, then click `Use Selected Phone`.
6. Click `Start Camera`.
7. In your conferencing app, choose `AVream Camera` (and optionally `AVream Mic`).

## CLI Quickstart

```bash
avream status
avream devices
avream start --mode wifi --lens front
avream camera stop
```

Full command reference: [CLI Reference](CLI_README.md).

## Install Options

- Recommended: `avream_<version>_amd64.deb` (single package).
- Advanced Debian split bundle: `avream-deb-split_<version>_amd64.tar.gz`.

Full guide: [Install and Upgrade](INSTALL.md).

## Documentation

- [User Guide](USER_GUIDE.md)
- [Install and Upgrade](INSTALL.md)
- [CLI Reference](CLI_README.md)
- [Troubleshooting](TROUBLESHOOTING.md)
- [FAQ](FAQ.md)
- [Supported Platforms](SUPPORTED_PLATFORMS.md)
- [API v1](API_V1.md)

Release and security references:

- [Release Checklist](RELEASE_CHECKLIST.md)
- [Release Template](RELEASE_TEMPLATE.md)
- [RC Drill](RC_DRILL.md)
- [Security Decisions](SECURITY_DECISIONS.md)

## Known Limits

- PC audio output to phone speaker is not in stable baseline.
- Preview runs as a separate `scrcpy` window, not embedded in GTK content.

## Releases

- Latest release: <https://github.com/Kacoze/avream/releases/latest>
