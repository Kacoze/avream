# AVream FAQ

## How do I use my Android phone as a webcam on Linux?

Install AVream `.deb`, enable `avreamd` user service, connect phone with USB debugging enabled, then in AVream click `Scan Phones` -> `Use Selected Phone` -> `Start Camera`.

## How do I use Android phone microphone on Linux?

Start camera in AVream, then choose `AVream Mic` inside your meeting/recording app.

## Does AVream work with Zoom, Google Meet, and OBS?

Yes. Select `AVream Camera` and `AVream Mic` in your app device settings.

## USB or Wi-Fi: which is better?

USB is usually more stable. Wi-Fi is convenient after initial setup and works best on reliable local networks.

## Why is AVream Camera not visible in my app?

Try `Reset Camera` in AVream, then start camera again. Verify `v4l2loopback` is installed. See `docs/TROUBLESHOOTING.md`.

## Why does AVream ask for password sometimes?

Some actions need elevated privileges via polkit (for example camera reset/reload). You can configure passwordless mode with `avream-passwordless-setup`.

## Can AVream send PC audio to phone speaker?

Not in stable baseline without additional software on phone. Current stable flow focuses on phone camera and phone mic as Linux devices.

## Is there a CLI?

Yes. Use `avream` for status, devices, camera start/stop, Wi-Fi setup, and mic control. See `docs/CLI_README.md`.
