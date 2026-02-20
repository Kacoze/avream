#!/usr/bin/env bash
set -euo pipefail

SUDO=(sudo)
if [ "${EUID}" -eq 0 ]; then
  SUDO=()
fi

target_user="${SUDO_USER:-${USER:-}}"
if [ -n "$target_user" ] && [ "$target_user" != "root" ]; then
  target_uid="$(id -u "$target_user" 2>/dev/null || true)"
  if [ -n "${target_uid}" ] && [ -d "/run/user/${target_uid}" ]; then
    runuser -u "$target_user" -- env \
      XDG_RUNTIME_DIR="/run/user/${target_uid}" \
      DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/${target_uid}/bus" \
      systemctl --user disable --now avreamd.service || true
  fi
fi

"${SUDO[@]}" apt-get remove -y avream avream-meta avream-daemon avream-ui avream-helper || true
"${SUDO[@]}" rm -f /etc/apt/sources.list.d/avream.list /usr/share/keyrings/avream-archive-keyring.gpg || true

echo "AVream packages removed."
