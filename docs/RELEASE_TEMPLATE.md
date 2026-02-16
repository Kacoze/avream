# AVream Release Notes Template

## Highlights

- <top user-visible changes>

## Upgrade Notes

- Package layout: <monolithic/split transition details>
- API compatibility: <removed endpoints and migration notes>
- Service behavior: <systemd user service changes>

## Known Issues

- <issue>
- <workaround>

## Installation

```bash
sudo apt install ./<package>.deb
```

## Verification

- Launch `avream-ui`
- Verify `/status` responds
- Verify phone detection (`/android/devices`)
- Start/stop camera and microphone from UI

## Support

- Attach daemon logs and exact UI error message to issue reports.
