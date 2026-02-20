#!/usr/bin/env bash
set -euo pipefail

ok=0
fail=0

check() {
  local name="$1"
  local cmd="$2"
  if bash -lc "$cmd" >/dev/null 2>&1; then
    printf 'OK   %s\n' "$name"
    ok=$((ok + 1))
  else
    printf 'FAIL %s\n' "$name"
    fail=$((fail + 1))
  fi
}

check "avream CLI available" "command -v avream"
check "avreamd available" "command -v avreamd"
check "avream-ui available" "command -v avream-ui"
check "user service enabled" "systemctl --user is-enabled avreamd.service"
check "user service active" "systemctl --user is-active avreamd.service"
check "daemon API reachable" "avream status"

printf '\nSummary: %d OK, %d FAIL\n' "$ok" "$fail"
if [ "$fail" -gt 0 ]; then
  exit 1
fi
