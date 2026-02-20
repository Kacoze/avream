# AVream Stable Release Checklist

Use this checklist before cutting a stable tag.

## Scope and Support

- Supported platforms documented (Ubuntu 22.04/24.04, Debian 12).
- Known limitations documented (Secure Boot, v4l2loopback specifics, desktop auth agent requirements).

## Quality Gates

- Python unit + integration tests are green in CI.
- Rust helper tests are green in CI.
- `.deb` smoke build/install/runtime checks are green in CI.

## User Experience

- First-run flow in GUI validated on fresh user profile.
- Phone detection and start flow validated over USB.
- Camera and microphone start/stop flows validated in common conferencing apps.

## Security and Privilege Model

- Helper allowlist reviewed.
- Helper parameter validation reviewed.
- Polkit mode decision confirmed (`auth_admin` vs `auth_admin_keep`).

## Packaging and Artifacts

- `.deb` contains daemon, UI, helper, desktop entry, metainfo, icon, policy.
- Release notes include upgrade notes for removed API endpoints.
- SHA256 checksum file is generated and published with release assets.
- `scripts/install.sh` one-liner path validated on clean host.
- APT repository metadata generated (`Packages`, `Release`, `InRelease`).
- APT signing secrets configured in GitHub Actions:
  - `AVREAM_APT_GPG_PRIVATE_KEY`
  - `AVREAM_APT_GPG_PASSPHRASE`
