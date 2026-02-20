#!/usr/bin/env bash
set -euo pipefail

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
    AVREAM_PLATFORM_STATUS="official"
    AVREAM_PLATFORM_FAMILY="debian"
  elif _avream_has_token "${AVREAM_OS_ID}" "linuxmint pop zorin neon elementary lmde mx"; then
    AVREAM_PLATFORM_STATUS="compatible"
    AVREAM_PLATFORM_FAMILY="debian"
  elif _avream_has_token "${AVREAM_OS_ID}" "fedora"; then
    AVREAM_PLATFORM_STATUS="official"
    AVREAM_PLATFORM_FAMILY="rpm"
  elif _avream_has_token "${AVREAM_OS_ID}" "opensuse opensuse-leap opensuse-tumbleweed sles rhel rocky almalinux"; then
    AVREAM_PLATFORM_STATUS="compatible"
    AVREAM_PLATFORM_FAMILY="rpm"
  elif _avream_has_token "${AVREAM_OS_ID}" "arch manjaro endeavouros"; then
    AVREAM_PLATFORM_STATUS="compatible"
    AVREAM_PLATFORM_FAMILY="arch"
  elif _avream_has_token "${AVREAM_OS_ID}" "nixos"; then
    AVREAM_PLATFORM_STATUS="compatible"
    AVREAM_PLATFORM_FAMILY="nix"
  elif _avream_has_token "debian" "$id_like" || _avream_has_token "ubuntu" "$id_like"; then
    AVREAM_PLATFORM_STATUS="compatible"
    AVREAM_PLATFORM_FAMILY="debian"
  elif _avream_has_token "rhel" "$id_like" || _avream_has_token "fedora" "$id_like" || _avream_has_token "suse" "$id_like"; then
    AVREAM_PLATFORM_STATUS="compatible"
    AVREAM_PLATFORM_FAMILY="rpm"
  elif _avream_has_token "arch" "$id_like"; then
    AVREAM_PLATFORM_STATUS="compatible"
    AVREAM_PLATFORM_FAMILY="arch"
  elif _avream_has_token "nixos" "$id_like"; then
    AVREAM_PLATFORM_STATUS="compatible"
    AVREAM_PLATFORM_FAMILY="nix"
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
    repo)
      AVREAM_INSTALL_PRIMARY="repo"
      ;;
    release)
      AVREAM_INSTALL_PRIMARY="release"
      ;;
    auto)
      case "$backend" in
        apt)
          AVREAM_INSTALL_PRIMARY="repo"
          AVREAM_INSTALL_FALLBACK="release"
          ;;
        dnf|zypper)
          AVREAM_INSTALL_PRIMARY="release"
          ;;
        pacman)
          AVREAM_INSTALL_PRIMARY="aur"
          ;;
        nix)
          AVREAM_INSTALL_PRIMARY="nix"
          ;;
        *)
          return 1
          ;;
      esac
      ;;
    *)
      return 1
      ;;
  esac
}
