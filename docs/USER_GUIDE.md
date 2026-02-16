# AVream User Guide

This guide covers the stable AVream flow for using an Android phone as webcam and microphone on Linux.

## 1) Install

Install the `.deb` package:

```bash
sudo apt install ./avream_<version>_amd64.deb
```

## 2) Enable daemon service (one-time)

```bash
mkdir -p ~/.config/avream
cp -n /usr/lib/systemd/user/avreamd.env ~/.config/avream/avreamd.env
systemctl --user daemon-reload
systemctl --user enable --now avreamd.service
```

## 3) Use phone as camera

1. Enable Developer Options and USB debugging on your phone.
2. Connect phone with USB, unlock it, and accept USB debugging prompt.
3. Open AVream.
4. If daemon lock screen appears, click **Enable AVream Service**.
5. Click **Scan Phones**.
6. Select the phone and click **Use Selected Phone**.
7. Choose **Camera lens**: Front or Back.
8. Optional: choose **Rotation** (0/90/180/270).
9. Optional: enable **Preview window** if you want a separate AVream preview window.
10. Preview window mode and rotation can be changed only when camera is stopped.
11. Click **Start Camera**.
12. In Zoom/Meet/OBS select **AVream Camera**.

AVream preview window uses scrcpy with AVream title and size settings.

## 4) Optional: use AVream microphone

AVream starts virtual microphone automatically when camera starts.

`AVream Mic` is fed from the phone microphone path. If you want your headset/laptop mic instead, select that host microphone directly in your app.

1. Click **Start Camera**.
2. In your app select **AVream Mic**.
3. Stopping camera also stops AVream microphone.

## 5) Optional: Wi-Fi mode

1. Select a USB-connected phone.
2. In **Connection mode**, choose **Wi-Fi** and click **Use Selected Phone** (AVream enables tcpip, detects phone IP, and connects).
3. Wait for endpoint to appear (for example `192.168.1.10:5555`).
4. You can disconnect USB and start camera with the Wi-Fi device.
5. If needed, fill endpoint field manually and use **Use Selected Phone** / **Disconnect Selected** (`IP` or `IP:PORT`).

CLI alternative for Wi-Fi setup:

```bash
avream wifi setup --serial <USB_SERIAL> --port 5555
avream start --mode wifi --lens front
```

## 6) Optional: disable auth prompts for AVream actions

By default, AVream may show a polkit password prompt for privileged actions (camera reset/reload).

Use GUI:
1. Open **Advanced** and use **Passwordless auth** section.
2. Click **Enable**.
3. Approve the polkit prompt.
4. Click **Check** to confirm status.

Use CLI:

```bash
avream-passwordless-setup status
pkexec avream-passwordless-setup enable --user "$USER"
```

To disable later:

```bash
pkexec avream-passwordless-setup disable --user "$USER"
```

## 7) Quick verification checklist

- `systemctl --user status avreamd.service` returns active/running.
- `avream devices` lists phone in `device` state.
- Meeting app shows `AVream Camera` and `AVream Mic`.

If something fails, see `docs/TROUBLESHOOTING.md`.

## 8) Updates

1. Click version label in bottom-left corner.
2. AVream checks latest release and opens update modal.
3. If update is available, modal shows **Install Update**.
4. AVream asks for confirmation, can stop active camera/mic, verifies checksums, installs update, and schedules daemon restart.
5. **Open Release** is always available in modal.
6. When update is available, bottom-left version indicator turns red and shows `current -> latest`.

## 9) Saved UI settings

AVream auto-saves recent UI connection settings and restores them on next launch.

Saved fields include:
- connection mode,
- lens and rotation,
- preview window mode,
- Wi-Fi endpoint,
- last selected phone identifiers (id/serial/ip hints).

In **Advanced -> UI settings**:
- **Save Settings** writes current values immediately,
- **Reset Saved** clears saved values and restores defaults.

Wi-Fi section also shows status of saved endpoint (`✓ connected` or `✗ not found/state`).
