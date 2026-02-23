# AVream Release Notes Template

## Highlights

- <top user-visible changes>

## Upgrade Notes

- Package layout: <monolithic/split/RPM/Arch/Nix notes>
- API compatibility: <removed endpoints and migration notes>
- Service behavior: <systemd user service changes>

## Known Issues

- <issue>
- <workaround>

## Installation

Debian/Ubuntu:

```bash
sudo apt install ./avream_<version>_amd64.deb
```

Fedora/openSUSE:

```bash
sudo dnf install ./avream-<version>-1.x86_64.rpm
# or
sudo zypper --non-interactive install ./avream-<version>-1.x86_64.rpm
```

Arch/Nix:
- Arch: AUR package `avream`
- Nix: `nix profile install github:Kacoze/avream#avream`

Snap/Flatpak:
- Snap: `sudo snap install avream --classic`
- Flatpak: `flatpak install -y flathub io.avream.AVream`

PPA (Ubuntu):

```bash
sudo add-apt-repository ppa:<owner>/<ppa-name>
sudo apt update
sudo apt install avream
```

## Verification

- Launch `avream-ui`
- Verify `/status` responds
- Verify phone detection (`/android/devices`)
- Start/stop camera and microphone from UI

## Support

- Attach daemon logs and exact UI error message to issue reports.
