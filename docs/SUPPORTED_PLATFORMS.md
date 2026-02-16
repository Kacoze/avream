# Supported Platforms

## Stable target (normal users)

- Ubuntu 22.04 (GNOME)
- Ubuntu 24.04 (GNOME)
- Debian 12

Architecture:
- amd64

## Required system capabilities

- systemd user services
- polkit and desktop auth agent
- Linux virtual video support (`v4l2loopback`)

## Runtime tools (feature-dependent)

- `scrcpy` + `adb` (Android camera backend)
- `pulseaudio-utils` or `pw-loopback` (audio virtual mic path)

## Out of scope for stable baseline

- Unsupported desktop stacks without auth agent
- Non-Linux platforms
- Non-amd64 builds (until explicitly added)
