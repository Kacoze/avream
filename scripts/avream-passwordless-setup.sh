#!/usr/bin/env bash
set -euo pipefail

RULE_PATH="/etc/polkit-1/rules.d/49-avream-noprompt.rules"
USERS_FILE="/etc/avream/passwordless-users.conf"
ACTION_ID="io.avream.helper.run"

usage() {
  cat <<'EOF'
Usage:
  avream-passwordless-setup <enable|disable|status> [--user USER] [--json]

Examples:
  avream-passwordless-setup status
  avream-passwordless-setup enable --user alice
  avream-passwordless-setup disable --user alice
EOF
}

json_escape() {
  python3 - <<'PY' "$1"
import json,sys
print(json.dumps(sys.argv[1]))
PY
}

user_allowed() {
  local user="$1"
  [ -f "$USERS_FILE" ] && grep -qx "$user" "$USERS_FILE"
}

rule_installed() {
  [ -f "$RULE_PATH" ] && grep -q "$ACTION_ID" "$RULE_PATH"
}

ensure_users_file() {
  install -d -m 0755 /etc/avream
  touch "$USERS_FILE"
  chmod 0644 "$USERS_FILE"
}

js_allowed_users_array() {
  python3 - <<'PY' "$USERS_FILE"
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
users = []
if path.exists():
    for line in path.read_text(encoding="utf-8").splitlines():
        name = line.strip()
        if name:
            users.append(name)
print(json.dumps(sorted(set(users))))
PY
}

ensure_rule() {
  local users_json
  users_json="$(js_allowed_users_array)"
  install -d -m 0755 /etc/polkit-1/rules.d
  cat > "$RULE_PATH" <<EOF
// Managed by AVream.
polkit.addRule(function(action, subject) {
  if (action.id != "$ACTION_ID") {
    return;
  }
  if (!subject.local || !subject.active) {
    return;
  }

  var allowed = $users_json;

  if (allowed.indexOf(subject.user) >= 0) {
    return polkit.Result.YES;
  }
});
EOF
  chmod 0644 "$RULE_PATH"
}

print_status() {
  local user="$1"
  local as_json="$2"
  local r="false"
  local m="false"
  local enabled="false"

  if rule_installed; then
    r="true"
  fi
  if user_allowed "$user"; then
    m="true"
  fi
  if [ "$r" = "true" ] && [ "$m" = "true" ]; then
    enabled="true"
  fi

  if [ "$as_json" = "true" ]; then
    printf '{"ok":true,"user":%s,"rule_installed":%s,"user_allowed":%s,"enabled":%s,"users_file":%s,"rule_path":%s}\n' \
      "$(json_escape "$user")" "$r" "$m" "$enabled" "$(json_escape "$USERS_FILE")" "$(json_escape "$RULE_PATH")"
    return 0
  fi

  echo "User: $user"
  echo "Rule installed: $r ($RULE_PATH)"
  echo "User allowed: $m ($USERS_FILE)"
  echo "Passwordless enabled: $enabled"
}

enable_passwordless() {
  local user="$1"
  ensure_users_file
  ensure_rule

  if ! user_allowed "$user"; then
    printf '%s\n' "$user" >> "$USERS_FILE"
    sort -u -o "$USERS_FILE" "$USERS_FILE"
  fi
  ensure_rule

  echo "Enabled passwordless AVream helper actions for user: $user"
  echo "Rule: $RULE_PATH"
  echo "Users: $USERS_FILE"
}

disable_passwordless() {
  local user="$1"
  if [ -f "$USERS_FILE" ]; then
    local tmp
    tmp=$(mktemp)
    grep -vx "$user" "$USERS_FILE" > "$tmp" || true
    mv "$tmp" "$USERS_FILE"
    chmod 0644 "$USERS_FILE"
  fi

  if [ -f "$USERS_FILE" ] && [ ! -s "$USERS_FILE" ]; then
    rm -f "$USERS_FILE"
    rm -f "$RULE_PATH"
  else
    ensure_rule
  fi

  echo "Disabled passwordless AVream helper actions for user: $user"
}

need_root() {
  local action="$1"
  if [ "$action" = "status" ]; then
    return 1
  fi
  if [ "$(id -u)" -eq 0 ]; then
    return 1
  fi
  return 0
}

reexec_as_root() {
  if command -v sudo >/dev/null 2>&1; then
    exec sudo "$0" "$@"
  fi
  if command -v pkexec >/dev/null 2>&1; then
    exec pkexec "$0" "$@"
  fi
  echo "Error: root privileges are required; install sudo or pkexec." >&2
  exit 1
}

main() {
  if [ "$#" -lt 1 ]; then
    usage
    exit 1
  fi

  local action="$1"
  shift
  local user="${SUDO_USER:-${USER:-}}"
  local as_json="false"

  while [ "$#" -gt 0 ]; do
    case "$1" in
      --user)
        if [ "$#" -lt 2 ]; then
          echo "Error: --user requires value" >&2
          exit 1
        fi
        user="$2"
        shift 2
        ;;
      --json)
        as_json="true"
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        echo "Error: unknown argument: $1" >&2
        usage
        exit 1
        ;;
    esac
  done

  if [ -z "$user" ] && [ -n "${PKEXEC_UID:-}" ]; then
    user="$(id -nu "${PKEXEC_UID}")"
  fi
  if [ -z "$user" ]; then
    echo "Error: could not determine target user; pass --user" >&2
    exit 1
  fi
  if ! id "$user" >/dev/null 2>&1; then
    echo "Error: user does not exist: $user" >&2
    exit 1
  fi

  if need_root "$action"; then
    if [ "$as_json" = "true" ]; then
      reexec_as_root "$action" --user "$user" --json
    else
      reexec_as_root "$action" --user "$user"
    fi
  fi

  case "$action" in
    enable)
      enable_passwordless "$user"
      ;;
    disable)
      disable_passwordless "$user"
      ;;
    status)
      print_status "$user" "$as_json"
      ;;
    *)
      echo "Error: unsupported action: $action" >&2
      usage
      exit 1
      ;;
  esac
}

main "$@"
