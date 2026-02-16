# AVream CLI Quick Reference

Use `avream` to control AVream without GUI.

If `avream` is missing after install, reinstall the package and refresh shell command cache:

```bash
sudo apt install --reinstall ./avream_<version>_amd64.deb
rehash
```

## Service control

```bash
systemctl --user daemon-reload
systemctl --user restart avreamd.service
systemctl --user status avreamd.service
```

## Common flow

```bash
avream status
avream devices
avream start --mode wifi --lens front
avream camera stop
```

## Command groups

Status and devices:

```bash
avream status
avream devices
```

One-shot start (recommended):

```bash
# Wi-Fi setup + camera start
avream start --mode wifi --lens front

# USB camera start
avream start --mode usb --serial <USB_SERIAL> --lens back
```

Camera controls:

```bash
avream camera start --serial <ADB_SERIAL_OR_IPPORT> --lens front --rotation 0 --preview-window
avream camera stop
avream camera reset
```

Wi-Fi controls:

```bash
avream wifi setup --serial <USB_SERIAL> --port 5555
avream wifi connect 192.168.1.10:5555
avream wifi disconnect 192.168.1.10:5555
```

Microphone controls:

```bash
avream mic start --backend pipewire
avream mic stop
```

Update controls:

```bash
avream update status
avream update check --force
avream update install --allow-stop-streams
avream update logs
avream update config get
avream update config set --auto-check daily --channel stable
```

JSON output and custom socket:

```bash
avream --json status
avream --socket-path /tmp/avream.sock status
```

## Passwordless helper mode (optional)

```bash
avream-passwordless-setup status --user "$USER"
pkexec avream-passwordless-setup enable --user "$USER"
pkexec avream-passwordless-setup disable --user "$USER"
```

For GUI-first setup, see `docs/USER_GUIDE.md`.
