# Security Decisions

## Dependency installation via helper

Decision for stable baseline:
- AVream helper does **not** install packages automatically.

Rationale:
- Keeps privileged helper surface minimal.
- Avoids distro-specific package-manager logic in root context.
- Reduces risk of privilege misuse and unintended package changes.

Current approach:
- Doctor and API errors provide package hints (`E_DEP_MISSING` details).
- User installs missing packages through distro tooling.

Future reconsideration (optional):
- Any helper-based install flow must use strict allowlists, distro gating, and explicit user confirmation.

## Optional passwordless privileged actions

Decision:
- AVream supports optional passwordless mode using a polkit rule scoped to AVream helper action `io.avream.helper.run` and explicit username allowlist.

Rationale:
- Keeps a single privilege model (polkit + helper).
- Avoids broad sudoers rules for generic commands.
- Scope is limited to local active session and explicit usernames enabled by admin.

Implementation notes:
- Setup tool: `avream-passwordless-setup`.
- Enable installs `/etc/polkit-1/rules.d/49-avream-noprompt.rules` and adds user to `/etc/avream/passwordless-users.conf`.
- Disable removes user from allowlist; if allowlist becomes empty, it removes the rule.
