# AVream

AVream lets you use your Android phone as a webcam and microphone on Linux.

It is built for real desktop calls and streams: Google Meet, Zoom, OBS, and any app that can read standard Linux virtual camera and mic devices.

Keywords: Android phone as webcam on Linux, Android as microphone on Linux, Linux virtual camera, USB/Wi-Fi phone camera bridge.

## Why AVream

- Phone-first flow: pick phone, start camera, select `AVream Camera` in your app.
- USB and Wi-Fi modes with practical reconnect behavior.
- Dedicated CLI (`avream`) and desktop GUI (`avream-ui`).
- Secure privilege model via polkit helper (no `sudo` in GUI actions).

## 5-Minute Quickstart

1. Download and install the monolithic package from Releases:

```bash
sudo apt install ./avream_1.0.0_amd64.deb
```

2. Enable daemon service once:

```bash
mkdir -p ~/.config/avream
cp -n /usr/lib/systemd/user/avreamd.env ~/.config/avream/avreamd.env
systemctl --user daemon-reload
systemctl --user enable --now avreamd.service
```

3. Connect phone with USB, unlock it, accept USB debugging prompt.
4. Launch GUI:

```bash
avream-ui
```

5. On first launch, if daemon is not active, click `Enable AVream Service`.
6. Click `Scan Phones` -> `Use Selected Phone` -> `Start Camera`.
7. In Meet/Zoom/OBS choose `AVream Camera` and (optionally) `AVream Mic`.

## CLI Quickstart

```bash
avream status
avream devices
avream start --mode wifi --lens front
avream camera stop
```

Full CLI reference: `docs/CLI_README.md`.

## Install Options

- Recommended for most users: monolithic package `avream_<version>_amd64.deb`.
- Advanced packaging: split packages (`avream-daemon`, `avream-ui`, `avream-helper`, `avream-meta`).

See `docs/INSTALL.md` for install, upgrade, and uninstall examples.

## Documentation

- User guide: `docs/USER_GUIDE.md`
- Install and upgrade: `docs/INSTALL.md`
- CLI reference: `docs/CLI_README.md`
- Troubleshooting: `docs/TROUBLESHOOTING.md`
- FAQ: `docs/FAQ.md`
- Supported platforms: `docs/SUPPORTED_PLATFORMS.md`
- API contract: `docs/API_V1.md`

Release and security docs:

- `docs/RELEASE_CHECKLIST.md`
- `docs/RELEASE_TEMPLATE.md`
- `docs/RC_DRILL.md`
- `docs/SECURITY_DECISIONS.md`

## Architecture

- `avreamd`: user daemon exposing JSON API over UNIX socket.
- `avream-ui`: GTK4/libadwaita desktop app.
- `avream-helper`: privileged helper via polkit.

## Known Limits

- Phone speaker output (PC audio -> phone speaker) is not part of stable baseline.
- Preview is a separate `scrcpy` window, not embedded in GTK content.

## Developer Notes

Build local packages:

```bash
bash scripts/build-deb.sh
bash scripts/build-deb-split.sh
```

Generated release docs are copied to `dist/` by `scripts/generate-dist-docs.sh`.
