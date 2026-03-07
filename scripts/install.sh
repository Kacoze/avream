#!/usr/bin/env bash
set -euo pipefail

_AVREAM_SCRIPT="${BASH_SOURCE[0]:-}"
if [ -n "$_AVREAM_SCRIPT" ] && [ -f "$(dirname "$_AVREAM_SCRIPT")/lib/install-platform.sh" ]; then
  SCRIPT_DIR="$(cd "$(dirname "$_AVREAM_SCRIPT")" && pwd)"
  source "${SCRIPT_DIR}/lib/install-platform.sh"
else
  # curl-pipe mode: platform lib inlined from scripts/lib/install-platform.sh.
  # Keep this block in sync with that file — no external fetch, no version skew.
  _avream_strip_quotes() {
    local raw="$1"
    raw="${raw%\"}"
    raw="${raw#\"}"
    printf '%s' "$raw"
  }

  _avream_has_token() {
    local needle="$1"
    local haystack="$2"
    for token in $haystack; do
      if [ "$token" = "$needle" ]; then
        return 0
      fi
    done
    return 1
  }

  avream_load_os_release() {
    local os_release_path="${1:-/etc/os-release}"
    if [ ! -f "$os_release_path" ]; then
      return 1
    fi
    AVREAM_OS_ID=""
    AVREAM_OS_ID_LIKE=""
    AVREAM_OS_NAME=""
    AVREAM_OS_PRETTY_NAME=""
    while IFS='=' read -r key value; do
      [ -z "$key" ] && continue
      [ "${key#\#}" != "$key" ] && continue
      value="$(_avream_strip_quotes "$value")"
      case "$key" in
        ID) AVREAM_OS_ID="${value,,}" ;;
        ID_LIKE) AVREAM_OS_ID_LIKE="${value,,}" ;;
        NAME) AVREAM_OS_NAME="$value" ;;
        PRETTY_NAME) AVREAM_OS_PRETTY_NAME="$value" ;;
      esac
    done <"$os_release_path"
    return 0
  }

  avream_detect_platform_support() {
    local os_release_path="${1:-/etc/os-release}"
    AVREAM_PLATFORM_STATUS="unsupported"
    AVREAM_PLATFORM_FAMILY="unknown"
    AVREAM_PLATFORM_LABEL="Unknown Linux"
    if ! avream_load_os_release "$os_release_path"; then
      return 1
    fi
    local id_like
    id_like="${AVREAM_OS_ID_LIKE:-}"
    if _avream_has_token "${AVREAM_OS_ID}" "debian ubuntu"; then
      AVREAM_PLATFORM_STATUS="official"; AVREAM_PLATFORM_FAMILY="debian"
    elif _avream_has_token "${AVREAM_OS_ID}" "linuxmint pop zorin neon elementary lmde mx"; then
      AVREAM_PLATFORM_STATUS="compatible"; AVREAM_PLATFORM_FAMILY="debian"
    elif _avream_has_token "${AVREAM_OS_ID}" "fedora"; then
      AVREAM_PLATFORM_STATUS="official"; AVREAM_PLATFORM_FAMILY="rpm"
    elif _avream_has_token "${AVREAM_OS_ID}" "opensuse opensuse-leap opensuse-tumbleweed sles rhel rocky almalinux"; then
      AVREAM_PLATFORM_STATUS="compatible"; AVREAM_PLATFORM_FAMILY="rpm"
    elif _avream_has_token "${AVREAM_OS_ID}" "arch manjaro endeavouros"; then
      AVREAM_PLATFORM_STATUS="compatible"; AVREAM_PLATFORM_FAMILY="arch"
    elif _avream_has_token "${AVREAM_OS_ID}" "nixos"; then
      AVREAM_PLATFORM_STATUS="compatible"; AVREAM_PLATFORM_FAMILY="nix"
    elif _avream_has_token "debian" "$id_like" || _avream_has_token "ubuntu" "$id_like"; then
      AVREAM_PLATFORM_STATUS="compatible"; AVREAM_PLATFORM_FAMILY="debian"
    elif _avream_has_token "rhel" "$id_like" || _avream_has_token "fedora" "$id_like" || _avream_has_token "suse" "$id_like"; then
      AVREAM_PLATFORM_STATUS="compatible"; AVREAM_PLATFORM_FAMILY="rpm"
    elif _avream_has_token "arch" "$id_like"; then
      AVREAM_PLATFORM_STATUS="compatible"; AVREAM_PLATFORM_FAMILY="arch"
    elif _avream_has_token "nixos" "$id_like"; then
      AVREAM_PLATFORM_STATUS="compatible"; AVREAM_PLATFORM_FAMILY="nix"
    fi
    if [ -n "${AVREAM_OS_PRETTY_NAME:-}" ]; then
      AVREAM_PLATFORM_LABEL="${AVREAM_OS_PRETTY_NAME}"
    elif [ -n "${AVREAM_OS_NAME:-}" ]; then
      AVREAM_PLATFORM_LABEL="${AVREAM_OS_NAME}"
    fi
    return 0
  }

  avream_resolve_install_method() {
    local method="$1"
    local backend="${2:-unknown}"
    AVREAM_INSTALL_PRIMARY=""
    AVREAM_INSTALL_FALLBACK=""
    case "$method" in
      repo)     AVREAM_INSTALL_PRIMARY="repo" ;;
      release)  AVREAM_INSTALL_PRIMARY="release" ;;
      snap)     AVREAM_INSTALL_PRIMARY="snap" ;;
      flatpak)  AVREAM_INSTALL_PRIMARY="flatpak" ;;
      aur)      AVREAM_INSTALL_PRIMARY="aur" ;;
      nix)      AVREAM_INSTALL_PRIMARY="nix" ;;
      auto)
        case "$backend" in
          apt)          AVREAM_INSTALL_PRIMARY="repo"; AVREAM_INSTALL_FALLBACK="release" ;;
          dnf|zypper)   AVREAM_INSTALL_PRIMARY="release" ;;
          pacman)       AVREAM_INSTALL_PRIMARY="aur" ;;
          nix)          AVREAM_INSTALL_PRIMARY="nix" ;;
          snap)         AVREAM_INSTALL_PRIMARY="snap" ;;
          flatpak)      AVREAM_INSTALL_PRIMARY="flatpak" ;;
          *)            return 1 ;;
        esac
        ;;
      *) return 1 ;;
    esac
  }
fi

REPO="${AVREAM_REPO:-Kacoze/avream}"
VERSION="${AVREAM_VERSION:-latest}"
METHOD="${AVREAM_INSTALL_METHOD:-auto}" # auto|repo|release|snap|flatpak|aur|nix
BACKEND_OVERRIDE="${AVREAM_INSTALL_BACKEND:-auto}"
DEB_ARCH_EXPECTED="${AVREAM_DEB_ARCH:-amd64}"
RPM_ARCH_EXPECTED="${AVREAM_RPM_ARCH:-x86_64}"
APT_SUITE="${AVREAM_APT_SUITE:-stable}"
APT_COMPONENT="${AVREAM_APT_COMPONENT:-main}"
APT_BRANCH="${AVREAM_APT_BRANCH:-apt-repo}"
OS_RELEASE_PATH="${AVREAM_OS_RELEASE_PATH:-/etc/os-release}"
SNAP_CHANNEL="${AVREAM_SNAP_CHANNEL:-stable}"
FLATPAK_REMOTE="${AVREAM_FLATPAK_REMOTE:-flathub}"
FLATPAK_REMOTE_URL="${AVREAM_FLATPAK_REMOTE_URL:-https://flathub.org/repo/flathub.flatpakrepo}"
FLATPAK_APP_ID="${AVREAM_FLATPAK_APP_ID:-io.avream.AVream}"

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
  elif command -v snap >/dev/null 2>&1; then
    PACKAGE_BACKEND="snap"
  elif command -v flatpak >/dev/null 2>&1; then
    PACKAGE_BACKEND="flatpak"
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
  if [ "${EUID}" -eq 0 ]; then
    # Running as root (e.g. sudo install.sh): use runuser to switch to target user
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
  else
    # Running as the target user directly (e.g. curl | bash)
    mkdir -p ~/.config/avream
    cp -n /usr/lib/systemd/user/avreamd.env ~/.config/avream/avreamd.env || true
    XDG_RUNTIME_DIR="/run/user/${target_uid}" \
      DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/${target_uid}/bus" \
      systemctl --user daemon-reload || true
    XDG_RUNTIME_DIR="/run/user/${target_uid}" \
      DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/${target_uid}/bus" \
      systemctl --user enable --now avreamd.service || true
  fi
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

install_from_snap() {
  if ! command -v snap >/dev/null 2>&1; then
    echo "snap is required for snap installation method." >&2
    return 1
  fi
  if [ "$VERSION" != "latest" ]; then
    warn "Snap installs by channel; specific AVREAM_VERSION is ignored for method=snap."
  fi
  "${SUDO[@]}" snap install avream --classic --channel "$SNAP_CHANNEL"
}

install_from_flatpak() {
  if ! command -v flatpak >/dev/null 2>&1; then
    echo "flatpak is required for flatpak installation method." >&2
    return 1
  fi
  if [ "$VERSION" != "latest" ]; then
    warn "Flatpak installs by remote state; specific AVREAM_VERSION is ignored for method=flatpak."
  fi
  if ! flatpak remotes --columns=name | grep -Fxq "$FLATPAK_REMOTE"; then
    "${SUDO[@]}" flatpak remote-add --if-not-exists "$FLATPAK_REMOTE" "$FLATPAK_REMOTE_URL"
  fi
  "${SUDO[@]}" flatpak install -y "$FLATPAK_REMOTE" "$FLATPAK_APP_ID"
}

run_smoke_checks() {
  case "$AVREAM_INSTALL_PRIMARY" in
    snap)
      /snap/bin/avreamd --help >/dev/null
      /snap/bin/avream --help >/dev/null
      ;;
    flatpak)
      flatpak info "$FLATPAK_APP_ID" >/dev/null
      flatpak run --command=avream "$FLATPAK_APP_ID" --help >/dev/null
      ;;
    *)
      avreamd --help >/dev/null
      avream --help >/dev/null
      if [ "$PACKAGE_BACKEND" = "apt" ] || [ "$PACKAGE_BACKEND" = "dnf" ] || [ "$PACKAGE_BACKEND" = "zypper" ]; then
        avream-ui --help >/dev/null
      fi
      ;;
  esac
}

main() {
  detect_package_backend
  if [ "$PACKAGE_BACKEND" = "unknown" ]; then
    echo "Unsupported host: no known package backend detected (apt/dnf/zypper/pacman/nix/snap/flatpak)." >&2
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
  elif [ "$AVREAM_INSTALL_PRIMARY" = "snap" ]; then
    install_from_snap
  elif [ "$AVREAM_INSTALL_PRIMARY" = "flatpak" ]; then
    install_from_flatpak
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
