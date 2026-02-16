# AVream

AVream is a Linux app for using your Android phone as a virtual camera and microphone.

This repository is a full rewrite (v2) with a daemon + GUI + privileged helper:
- `avreamd` (daemon, user service, JSON API over UNIX socket)
- `avream-ui` (GTK4/libadwaita GUI, talks only to daemon)
- `avream-helper` (privileged helper via polkit; no sudo in GUI)

Legacy (previous bash-based project) is kept for reference in:
- `legacy/android-webcam-linux/`

## Current Implementation Snapshot

Implemented in this branch:
- Daemon API over UNIX socket focused on phone workflows (`/status`, `/video/*`, `/audio/*`, `/android/*`)
- Android video backend (`adb` + `scrcpy`) with process supervision
- Virtual microphone manager (PipeWire preferred, `snd_aloop` fallback)
- Privileged helper scaffold in Rust (`helper/`) + polkit policy
- GTK UI focused on phone actions: scan device, use selected phone, start/stop camera, start/stop microphone

## Developer Quickstart (current MVP)

Daemon (requires Python + `aiohttp`):

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -e .

avreamd
```

API check:

```bash
curl --unix-socket "$XDG_RUNTIME_DIR/avream/daemon.sock" http://localhost/status
```

GUI (requires GTK4 + libadwaita + PyGObject bindings):

```bash
python3 -m pip install -e ./ui
avream-ui
```

Helper:
- Rust toolchain (`cargo`) is required to build `helper/`.
- Optional passwordless mode setup tool: `avream-passwordless-setup`.

## Packaging (Debian/Ubuntu)

Debian package build scripts:

```bash
bash scripts/build-deb.sh
bash scripts/build-deb-split.sh
```

This produces development packages in `dist/`.

Release documentation is generated to `dist/` as part of release/deb artifact workflows:
- `dist/README_USER.md`
- `dist/API_MINIMAL.md`
- `dist/UPGRADE_NOTES.md`

The package currently installs:
- `avreamd` daemon CLI and Python modules
- `avream-ui` GUI CLI and Python modules
- `avream-helper` in `/usr/libexec`
- `avream-passwordless-setup` in `/usr/bin`
- user systemd unit (`avreamd.service`) and env file
- polkit policy, desktop entry, AppStream metadata, and icon

Split packaging mode additionally produces:
- `avream-daemon_<version>_amd64.deb`
- `avream-ui_<version>_amd64.deb`
- `avream-helper_<version>_amd64.deb`
- `avream-meta_<version>_amd64.deb` (transitional meta-package)

After installing the package, enable the user daemon:

```bash
mkdir -p ~/.config/avream
cp -n /usr/lib/systemd/user/avreamd.env ~/.config/avream/avreamd.env
systemctl --user daemon-reload
systemctl --user enable --now avreamd.service
```

User-facing docs:
- `docs/USER_GUIDE.md`
- `docs/TROUBLESHOOTING.md`
- `docs/SUPPORTED_PLATFORMS.md`

Release/security docs:
- `docs/RELEASE_CHECKLIST.md`
- `docs/RELEASE_TEMPLATE.md`
- `docs/RC_DRILL.md`
- `docs/SECURITY_DECISIONS.md`
