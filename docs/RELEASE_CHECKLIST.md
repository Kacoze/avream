# AVream Stable Release Checklist

Use this checklist before cutting a stable tag.

## Scope and Support

- Supported platforms documented (Tier A and Tier B in `docs/SUPPORTED_PLATFORMS.md`).
- Known limitations documented (Secure Boot, v4l2loopback specifics, desktop auth agent requirements).

## Quality Gates

- Python unit + integration tests are green in CI.
- Installer compatibility tests for Debian-family `os-release` fixtures are green.
- Rust helper tests are green in CI.
- `.deb` smoke build/install/runtime checks are green in CI.
- Nightly Debian-family idempotence matrix is green (or last failure analyzed and accepted before release).
- Release workflow `release-gate` job is green before assets are published.

## User Experience

- Manual UX validation is exception-based (not mandatory every patch release).
- Run manual checks only when high-risk areas changed:
  - device discovery/connect logic,
  - video/audio runtime pipeline,
  - polkit/helper behavior,
  - installer behavior not covered by existing automated tests.
- When no high-risk areas changed and all automated gates are green, manual QA can be skipped.

## Security and Privilege Model

- Helper allowlist reviewed.
- Helper parameter validation reviewed.
- Polkit mode decision confirmed (`auth_admin` vs `auth_admin_keep`).

## Packaging and Artifacts

- `.deb` contains daemon, UI, helper, desktop entry, metainfo, icon, policy.
- Release notes include upgrade notes for removed API endpoints.
- SHA256 checksum file is generated and published with release assets.
- `scripts/install.sh` one-liner logic validated by automated platform fixtures and release gate smoke checks.
- APT repository metadata generated (`Packages`, `Release`, `InRelease`).
- APT signing secrets configured in GitHub Actions:
  - `AVREAM_APT_GPG_PRIVATE_KEY`
  - `AVREAM_APT_GPG_PASSPHRASE`
