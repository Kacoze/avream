# Changelog

All notable changes to AVream will be documented in this file.

The format is based on Keep a Changelog.

## [Unreleased]

- Android video backend now supports profile-driven source selection with preferred device serial and preferred transport (USB/WiFi).
- Android selection now reports a clearer error when a preferred serial is present but not authorized/ready.
- Audio backend now supports a native PipeWire fallback path via `pw-loopback` when `pactl` is unavailable.
- Doctor now includes additional audio readiness checks (`pulseaudio_compat.available`, `pipewire.loopback_tool`, `audio.avream_mic_present`).
- UI UX hardening: progress feedback for long actions, structured profile/source forms, dialog-based errors, and log filter/copy actions.
- GUI logs now merge daemon SSE stream with local UI action logs while preserving filtering.
- Debian packaging now includes `avream-ui`, desktop entry, and service env file in addition to daemon/helper assets.
- UI v1.1 stabilization: stricter source/profile form validation and broader action-button busy locking.
- Added API contract integration tests covering envelope shape, request-id echo, and validation paths.
- Debian package now includes maintainer scripts (`postinst`, `prerm`) and CI runs a package sanity check before uploading artifacts.
- Observability v2: API middleware now logs request lifecycle with correlation id (`rid`) and latency.
- Log export bundle now includes `meta/runtime.json` and `meta/environment.json` for faster support triage.
- Helper/polkit hardening: strict helper param validation, privileged action allowlist in daemon client, and clearer auth-denied hints.
- Polkit policy now requires fresh admin authentication (`auth_admin`) for active sessions.
- CI now runs Python tests on 3.11 and 3.12 and builds a `.deb` smoke artifact for pull requests.
- Doctor full now includes runtime snapshot details and (optionally) helper status checks without forcing interactive pkexec.
- Support bundle now includes `doctor/full.json` and a `meta/summary.txt` quick triage file.
- Project version baseline renamed to `1.0.0` across Python, helper, and packaging/CI defaults.
- Added profile-level source binding (`video.source_id`) support across daemon/UI flow and backend source selection.
- UI now includes daemon-start command copy helpers, quick pattern setup flow, and quick camera verification messaging.
- Added AppStream metadata and application icon to Debian packaging.
- Added split-package build/check scripts for `avream-daemon`, `avream-ui`, and `avream-helper` with transitional meta package.
- Added user-facing docs: user guide, troubleshooting, supported platforms, and RC drill process.

## [2.0.0-alpha.2] - 2026-02-13

- GUI now uses full SSE log streaming (`/logs/stream`) instead of periodic polling.
- Added strict Debian package artifact workflow (`.deb`) in CI (`deb-artifact.yml`).
- Added API payload validation helpers and schema migrations for config/profiles/sources.
- Hardened integration tests for CI stability (mock helper/tool behavior).

## [2.0.0-alpha.1] - 2026-02-13

- New v2 rewrite: `avreamd` daemon exposing JSON API over UNIX socket.
- Added `avream-helper` privileged helper (Rust) + polkit policy.
- Added GTK4/libadwaita UI MVP (`avream-ui`).
- Implemented Android video backend (adb + scrcpy) + v4l2loopback integration.
- Implemented audio v1: PipeWire virtual mic via `pactl` modules, snd-aloop fallback via helper.
- Added Doctor checks, Fix actions, log export, logs tail/stream endpoints.
- Added CI workflow, dev install scripts, and experimental .deb build script.
