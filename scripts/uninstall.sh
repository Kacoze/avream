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
    if [ "${EUID}" -eq 0 ]; then
      # Running as root (e.g. sudo): use runuser to switch to the target user
      runuser -u "$target_user" -- env \
        XDG_RUNTIME_DIR="/run/user/${target_uid}" \
        DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/${target_uid}/bus" \
        systemctl --user disable --now avreamd.service || true
    else
      # Running as the target user directly (e.g. curl | bash)
      XDG_RUNTIME_DIR="/run/user/${target_uid}" \
        DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/${target_uid}/bus" \
        systemctl --user disable --now avreamd.service || true
    fi
  fi
fi

if command -v apt-get >/dev/null 2>&1; then
  "${SUDO[@]}" apt-get remove -y avream avream-meta avream-daemon avream-ui avream-helper || true
  "${SUDO[@]}" rm -f /etc/apt/sources.list.d/avream.list /usr/share/keyrings/avream-archive-keyring.gpg || true
fi

if command -v dnf >/dev/null 2>&1; then
  "${SUDO[@]}" dnf remove -y avream || true
fi

if command -v zypper >/dev/null 2>&1; then
  "${SUDO[@]}" zypper --non-interactive remove avream || true
fi

if command -v pacman >/dev/null 2>&1; then
  "${SUDO[@]}" pacman -R --noconfirm avream avream-bin || true
fi

if command -v nix-env >/dev/null 2>&1; then
  nix-env -e avream || true
fi

if command -v snap >/dev/null 2>&1; then
  "${SUDO[@]}" snap remove avream || true
fi

if command -v flatpak >/dev/null 2>&1; then
  "${SUDO[@]}" flatpak uninstall -y io.avream.AVream || true
fi

echo "AVream packages removed."
