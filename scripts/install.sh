#!/usr/bin/env bash
set -euo pipefail

REPO="${AVREAM_REPO:-Kacoze/avream}"
VERSION="${AVREAM_VERSION:-latest}"
METHOD="${AVREAM_INSTALL_METHOD:-auto}" # auto|repo|release
ARCH_EXPECTED="${AVREAM_DEB_ARCH:-amd64}"
APT_SUITE="${AVREAM_APT_SUITE:-stable}"
APT_COMPONENT="${AVREAM_APT_COMPONENT:-main}"
APT_BRANCH="${AVREAM_APT_BRANCH:-apt-repo}"

if ! command -v apt-get >/dev/null 2>&1; then
  echo "This installer supports Debian/Ubuntu (apt) only." >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required." >&2
  exit 1
fi

arch="$(dpkg --print-architecture)"
if [ "$arch" != "$ARCH_EXPECTED" ]; then
  echo "Unsupported architecture: $arch (expected: $ARCH_EXPECTED)." >&2
  exit 1
fi

SUDO=(sudo)
if [ "${EUID}" -eq 0 ]; then
  SUDO=()
fi

tmpdir="$(mktemp -d)"
cleanup() {
  rm -rf "$tmpdir"
}
trap cleanup EXIT

apt_repo_base="https://raw.githubusercontent.com/${REPO}/${APT_BRANCH}/apt"
apt_keyring="/usr/share/keyrings/avream-archive-keyring.gpg"
apt_list="/etc/apt/sources.list.d/avream.list"

log() {
  printf '%s\n' "$*"
}

warn() {
  printf 'WARN: %s\n' "$*" >&2
}

setup_user_service() {
  local target_user target_uid
  target_user="${SUDO_USER:-${USER:-}}"
  if [ -z "$target_user" ] || [ "$target_user" = "root" ]; then
    warn "Could not detect non-root target user. Skipping user service enable."
    return 0
  fi

  target_uid="$(id -u "$target_user" 2>/dev/null || true)"
  if [ -z "$target_uid" ] || [ ! -d "/run/user/${target_uid}" ]; then
    warn "No active user runtime for ${target_user}. Skipping automatic daemon enable."
    return 0
  fi

  log "Configuring avreamd user service for ${target_user}..."
  runuser -u "$target_user" -- bash -lc "mkdir -p ~/.config/avream"
  runuser -u "$target_user" -- bash -lc "cp -n /usr/lib/systemd/user/avreamd.env ~/.config/avream/avreamd.env || true"
  runuser -u "$target_user" -- env \
    XDG_RUNTIME_DIR="/run/user/${target_uid}" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/${target_uid}/bus" \
    systemctl --user daemon-reload || true
  runuser -u "$target_user" -- env \
    XDG_RUNTIME_DIR="/run/user/${target_uid}" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/${target_uid}/bus" \
    systemctl --user enable --now avreamd.service || true
}

install_from_release() {
  local api_url payload deb_url deb_path version_hint
  if [ "$VERSION" = "latest" ]; then
    api_url="https://api.github.com/repos/${REPO}/releases/latest"
    version_hint="latest"
  else
    case "$VERSION" in
      v*) api_url="https://api.github.com/repos/${REPO}/releases/tags/${VERSION}" ;;
      *) api_url="https://api.github.com/repos/${REPO}/releases/tags/v${VERSION}" ;;
    esac
    version_hint="$VERSION"
  fi

  log "Resolving AVream release (${version_hint})..."
  payload="$(curl -fsSL "$api_url")"
  deb_url="$(printf '%s\n' "$payload" | grep -Eo 'https://[^"]*/avream_[^"]*_amd64\.deb' | head -n1 || true)"
  if [ -z "$deb_url" ]; then
    echo "Could not find monolithic .deb asset in release metadata." >&2
    return 1
  fi

  deb_path="${tmpdir}/avream_${ARCH_EXPECTED}.deb"
  log "Downloading package..."
  curl -fsSL "$deb_url" -o "$deb_path"
  "${SUDO[@]}" apt-get update -y
  "${SUDO[@]}" apt-get install -y "$deb_path"
}

install_from_repo() {
  log "Configuring AVream APT repository..."
  "${SUDO[@]}" mkdir -p /usr/share/keyrings /etc/apt/sources.list.d
  curl -fsSL "${apt_repo_base}/avream-archive-keyring.gpg" | "${SUDO[@]}" tee "$apt_keyring" >/dev/null
  echo "deb [arch=${ARCH_EXPECTED} signed-by=${apt_keyring}] ${apt_repo_base} ${APT_SUITE} ${APT_COMPONENT}" | "${SUDO[@]}" tee "$apt_list" >/dev/null
  "${SUDO[@]}" apt-get update -y
  "${SUDO[@]}" apt-get install -y avream
}

run_smoke_checks() {
  avreamd --help >/dev/null
  avream-ui --help >/dev/null
}

main() {
  case "$METHOD" in
    repo)
      install_from_repo
      ;;
    release)
      install_from_release
      ;;
    auto)
      if ! install_from_repo; then
        warn "APT repository install failed; falling back to GitHub Release package."
        "${SUDO[@]}" rm -f "$apt_list" "$apt_keyring" >/dev/null 2>&1 || true
        install_from_release
      fi
      ;;
    *)
      echo "Unknown AVREAM_INSTALL_METHOD: $METHOD" >&2
      exit 1
      ;;
  esac

  setup_user_service
  run_smoke_checks
  log ""
  log "AVream installation finished."
  log "Run: avream-ui"
}

main "$@"
