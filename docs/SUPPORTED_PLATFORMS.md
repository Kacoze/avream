# Supported Platforms

## Stable target (normal users)

- Ubuntu 22.04 (GNOME)
- Ubuntu 24.04 (GNOME)
- Debian 12

Architecture:
- amd64

## Tested usage profile

- Linux desktop session with user systemd services enabled.
- Android phone with Developer Options and USB debugging.
- Conferencing/recording apps that accept standard V4L2 camera and Pulse/PipeWire microphone.

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

## Out of scope for stable baseline

- Unsupported desktop stacks without auth agent
- Non-Linux platforms
- Non-amd64 builds (until explicitly added)
