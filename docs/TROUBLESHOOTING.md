# AVream Troubleshooting

Use this page when Android webcam/microphone setup on Linux is not working as expected.

## Daemon unreachable

Run:

```bash
systemctl --user daemon-reload
systemctl --user enable --now avreamd.service
systemctl --user status avreamd.service
```

## No phone detected

- Use USB cable (data-capable).
- Enable USB debugging.
- Unlock phone and accept debugging authorization prompt.
- Run `adb devices` and confirm state is `device`.

Quick check:

```bash
avream devices
```

## Phone detected as unauthorized/offline

- Reconnect USB cable.
- Revoke USB debugging authorizations on phone and re-authorize.
- Restart adb server:

```bash
adb kill-server
adb start-server
adb devices
```

## Wi-Fi setup/connect fails

- Select USB phone, switch mode to **Wi-Fi**, then click **Use Selected Phone**.
- Ensure phone and computer are on the same local network.
- Verify endpoint manually:

```bash
adb connect <IP>:5555
adb devices
```

- If endpoint changed (DHCP), run **Setup Wi-Fi** again.

CLI fallback:

```bash
avream wifi setup --serial <USB_SERIAL> --port 5555
avream wifi connect <IP>:5555
```

## No AVream Camera in apps

- Click **Reset Camera** in AVream, then start camera again.
- Ensure `v4l2loopback` is installed (`v4l2loopback-dkms` on Debian/Ubuntu).
- Close apps already using `/dev/video*` and retry.

CLI fallback:

```bash
avream camera stop
avream camera reset
avream camera start --lens front
```

## Preview not visible in AVream window

- Camera streaming may still work even when preview window is unavailable.
- Preview window relies on `scrcpy` (separate window), not embedded GTK preview.
- Ensure `scrcpy` is installed and available in PATH.
- Restart AVream after installing `scrcpy`:

```bash
sudo apt install scrcpy
```

## Microphone does not appear

- Start camera in AVream first (mic follows camera lifecycle).
- Install missing tools: `pulseaudio-utils` and/or `pipewire-bin`.

## Polkit / authorization issues

- Ensure desktop authentication agent is running.
- If errors mention `pkexec` setuid, set `AVREAM_HELPER_MODE=systemd-run` in `~/.config/avream/avreamd.env` and restart user service.

## Passwordless mode not active after enabling

- Check status: `avream-passwordless-setup status`.
- Confirm rule exists: `/etc/polkit-1/rules.d/49-avream-noprompt.rules`.
- Confirm your user is present in `/etc/avream/passwordless-users.conf`.
- Ensure daemon uses `pkexec` runner:

```bash
systemctl --user show-environment | grep AVREAM_HELPER_MODE
```

If needed, set in `~/.config/avream/avreamd.env`:

```bash
AVREAM_HELPER_MODE=pkexec
```

Then restart daemon:

```bash
systemctl --user daemon-reload
systemctl --user restart avreamd.service
```

To disable passwordless mode:

```bash
pkexec avream-passwordless-setup disable --user "$USER"
```
