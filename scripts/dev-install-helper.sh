#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

HELPER_DIR="$ROOT_DIR/helper"
POLICY_SRC="$ROOT_DIR/packaging/polkit/io.avream.helper.policy"

HELPER_DST="${AVREAM_HELPER_DST:-/usr/libexec/avream-helper}"
POLICY_DST="${AVREAM_POLKIT_POLICY_DST:-/usr/share/polkit-1/actions/io.avream.helper.policy}"

if ! command -v cargo >/dev/null 2>&1; then
  echo "Error: cargo not found (install Rust toolchain)" >&2
  exit 1
fi

(cd "$HELPER_DIR" && cargo build --release)

install_with_sudo() {
  sudo install -D -m 0755 "$HELPER_DIR/target/release/avream-helper" "$HELPER_DST"
  sudo install -D -m 0644 "$POLICY_SRC" "$POLICY_DST"
}

install_with_pkexec() {
  pkexec install -D -m 0755 "$HELPER_DIR/target/release/avream-helper" "$HELPER_DST"
  pkexec install -D -m 0644 "$POLICY_SRC" "$POLICY_DST"
}

if command -v sudo >/dev/null 2>&1; then
  if sudo -n true >/dev/null 2>&1; then
    install_with_sudo
  else
    if [ -t 0 ] && [ -t 1 ]; then
      install_with_sudo
    elif command -v pkexec >/dev/null 2>&1; then
      install_with_pkexec
    else
      echo "Error: need root to install helper/polkit policy, but no interactive sudo and no pkexec available." >&2
      echo "Run manually in a terminal:" >&2
      echo "  sudo install -D -m 0755 '$HELPER_DIR/target/release/avream-helper' '$HELPER_DST'" >&2
      echo "  sudo install -D -m 0644 '$POLICY_SRC' '$POLICY_DST'" >&2
      exit 1
    fi
  fi
elif command -v pkexec >/dev/null 2>&1; then
  install_with_pkexec
else
  echo "Error: sudo or pkexec is required to install helper" >&2
  exit 1
fi

echo "Installed helper to: $HELPER_DST"
echo "Installed polkit policy to: $POLICY_DST"
