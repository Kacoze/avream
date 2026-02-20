#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/install-platform.sh"

REPO="${AVREAM_REPO:-Kacoze/avream}"
VERSION="${AVREAM_VERSION:-latest}"
METHOD="${AVREAM_INSTALL_METHOD:-auto}" # auto|repo|release
BACKEND_OVERRIDE="${AVREAM_INSTALL_BACKEND:-auto}"
DEB_ARCH_EXPECTED="${AVREAM_DEB_ARCH:-amd64}"
RPM_ARCH_EXPECTED="${AVREAM_RPM_ARCH:-x86_64}"
APT_SUITE="${AVREAM_APT_SUITE:-stable}"
APT_COMPONENT="${AVREAM_APT_COMPONENT:-main}"
APT_BRANCH="${AVREAM_APT_BRANCH:-apt-repo}"
OS_RELEASE_PATH="${AVREAM_OS_RELEASE_PATH:-/etc/os-release}"

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required." >&2
  exit 1
fi

if ! avream_detect_platform_support "$OS_RELEASE_PATH"; then
  echo "Could not read ${OS_RELEASE_PATH}. Cannot detect Linux distribution." >&2
  exit 1
fi

case "${AVREAM_PLATFORM_STATUS}" in
  official)
    ;;
  compatible)
    printf 'WARN: Detected %s (%s); using compatibility mode for %s systems.\n' "${AVREAM_PLATFORM_LABEL}" "${AVREAM_OS_ID}" "${AVREAM_PLATFORM_FAMILY}" >&2
    ;;
  *)
    echo "Unsupported distribution: ${AVREAM_PLATFORM_LABEL} (${AVREAM_OS_ID:-unknown})." >&2
    exit 1
    ;;
esac

machine_arch="$(uname -m)"
if [ "$machine_arch" != "x86_64" ] && [ "$machine_arch" != "amd64" ]; then
  echo "Unsupported architecture: $machine_arch (expected x86_64/amd64)." >&2
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
PACKAGE_BACKEND="unknown"

log() {
  printf '%s\n' "$*"
}

warn() {
  printf 'WARN: %s\n' "$*" >&2
}

detect_package_backend() {
  if [ "$BACKEND_OVERRIDE" != "auto" ]; then
    PACKAGE_BACKEND="$BACKEND_OVERRIDE"
    return 0
  fi

  if command -v apt-get >/dev/null 2>&1; then
    PACKAGE_BACKEND="apt"
  elif command -v dnf >/dev/null 2>&1; then
    PACKAGE_BACKEND="dnf"
  elif command -v zypper >/dev/null 2>&1; then
    PACKAGE_BACKEND="zypper"
  elif command -v pacman >/dev/null 2>&1; then
    PACKAGE_BACKEND="pacman"
  elif command -v nix >/dev/null 2>&1 || command -v nix-env >/dev/null 2>&1; then
    PACKAGE_BACKEND="nix"
  fi
}

resolve_release_api_url() {
  if [ "$VERSION" = "latest" ]; then
    printf '%s\n' "https://api.github.com/repos/${REPO}/releases/latest"
  else
    case "$VERSION" in
      v*) printf '%s\n' "https://api.github.com/repos/${REPO}/releases/tags/${VERSION}" ;;
      *) printf '%s\n' "https://api.github.com/repos/${REPO}/releases/tags/v${VERSION}" ;;
    esac
  fi
}

resolve_release_asset_url() {
  local payload="$1"
  case "$PACKAGE_BACKEND" in
    apt)
      printf '%s\n' "$payload" | grep -Eo "https://[^\"]*/avream_[^\"]*_${DEB_ARCH_EXPECTED}\\.deb" | head -n1 || true
      ;;
    dnf|zypper)
      printf '%s\n' "$payload" | grep -Eo "https://[^\"]*/avream[-_][^\"]*\\.${RPM_ARCH_EXPECTED}\\.rpm" | head -n1 || true
      ;;
    *)
      printf '\n'
      ;;
  esac
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
  local api_url payload pkg_url pkg_path version_hint
  api_url="$(resolve_release_api_url)"
  version_hint="${VERSION}"

  log "Resolving AVream release (${version_hint})..."
  payload="$(curl -fsSL "$api_url")"
  pkg_url="$(resolve_release_asset_url "$payload")"
  if [ -z "$pkg_url" ]; then
    echo "Could not find a compatible release package for backend ${PACKAGE_BACKEND}." >&2
    return 1
  fi

  pkg_path="${tmpdir}/$(basename "$pkg_url")"
  log "Downloading package..."
  curl -fsSL "$pkg_url" -o "$pkg_path"
  case "$PACKAGE_BACKEND" in
    apt)
      "${SUDO[@]}" apt-get update -y
      "${SUDO[@]}" apt-get install -y "$pkg_path"
      ;;
    dnf)
      "${SUDO[@]}" dnf install -y python3-aiohttp || true
      "${SUDO[@]}" dnf install -y "$pkg_path"
      ;;
    zypper)
      "${SUDO[@]}" zypper --non-interactive install python3-aiohttp || true
      "${SUDO[@]}" zypper --non-interactive install "$pkg_path"
      ;;
    *)
      echo "Release install is not supported for backend ${PACKAGE_BACKEND}." >&2
      return 1
      ;;
  esac
}

install_from_repo() {
  if [ "$PACKAGE_BACKEND" != "apt" ]; then
    echo "Repository install currently supports apt only." >&2
    return 1
  fi
  log "Configuring AVream APT repository..."
  "${SUDO[@]}" mkdir -p /usr/share/keyrings /etc/apt/sources.list.d
  curl -fsSL "${apt_repo_base}/avream-archive-keyring.gpg" | "${SUDO[@]}" tee "$apt_keyring" >/dev/null
  echo "deb [arch=${DEB_ARCH_EXPECTED} signed-by=${apt_keyring}] ${apt_repo_base} ${APT_SUITE} ${APT_COMPONENT}" | "${SUDO[@]}" tee "$apt_list" >/dev/null
  "${SUDO[@]}" apt-get update -y
  "${SUDO[@]}" apt-get install -y avream
}

run_smoke_checks() {
  avreamd --help >/dev/null
  avream --help >/dev/null
  if [ "$PACKAGE_BACKEND" = "apt" ]; then
    avream-ui --help >/dev/null
  fi
}

main() {
  detect_package_backend
  if [ "$PACKAGE_BACKEND" = "unknown" ]; then
    echo "Unsupported host: no known package manager detected (apt/dnf/zypper/pacman)." >&2
    exit 1
  fi

  if ! avream_resolve_install_method "$METHOD" "$PACKAGE_BACKEND"; then
    echo "Unknown AVREAM_INSTALL_METHOD: $METHOD" >&2
    exit 1
  fi

  case "$AVREAM_INSTALL_PRIMARY" in
    aur)
      echo "Arch-family installation uses AUR. Install with: yay -S avream (or paru -S avream)." >&2
      exit 1
      ;;
    nix)
      echo "Nix installation is provided via flake. See docs/INSTALL.md for nix profile command." >&2
      exit 1
      ;;
  esac

  if [ "$AVREAM_INSTALL_PRIMARY" = "repo" ]; then
    if ! install_from_repo; then
      if [ "$AVREAM_INSTALL_FALLBACK" = "release" ]; then
        warn "APT repository install failed; falling back to GitHub Release package."
        "${SUDO[@]}" rm -f "$apt_list" "$apt_keyring" >/dev/null 2>&1 || true
        install_from_release
      else
        exit 1
      fi
    fi
  elif [ "$AVREAM_INSTALL_PRIMARY" = "release" ]; then
    install_from_release
  else
    echo "Unsupported installer strategy: ${AVREAM_INSTALL_PRIMARY}" >&2
    exit 1
  fi

  setup_user_service
  run_smoke_checks
  log ""
  log "AVream installation finished."
  log "Run: avream-ui"
}

main "$@"
