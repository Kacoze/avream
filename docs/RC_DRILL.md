# AVream Release Candidate Drill

This document defines the RC process before stable release.

## RC cadence

- RC1: feature freeze + install and first-run validation.
- RC2: bugfix-only + support bundle quality validation.

## Exit criteria

- No open blocker or critical issues on supported platforms.
- CI matrix green.
- `.deb` install + runtime smoke green.
- User guide and troubleshooting docs updated.

## Bug triage SLA (during RC)

- Blocker: triage same day.
- Critical: triage within 24h.
- Major: triage within 48h.

## Mandatory manual checks

- Fresh install and first-run flow.
- Profile switching with explicit source binding.
- Doctor quick/full and support bundle export.
- Android backend start/stop and reconnect controls.

## Release sign-off

- Sign-off by maintainer for: UX, packaging, security/polkit, docs.
