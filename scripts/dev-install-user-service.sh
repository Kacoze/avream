#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

VENV_DIR="${AVREAM_VENV_DIR:-$HOME/.local/share/avream/venv}"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
SERVICE_PATH="$SYSTEMD_USER_DIR/avreamd.service"
ENV_DIR="$HOME/.config/avream"
ENV_FILE="$ENV_DIR/avreamd.env"

mkdir -p "$SYSTEMD_USER_DIR" "$ENV_DIR" "$(dirname "$VENV_DIR")"

if [ ! -x "$VENV_DIR/bin/python" ]; then
  python3 -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install --upgrade pip >/dev/null
"$VENV_DIR/bin/pip" install -e "$ROOT_DIR" >/dev/null

cat > "$SERVICE_PATH" <<EOF
[Unit]
Description=AVream daemon (user)
After=default.target

[Service]
Type=simple
EnvironmentFile=-%h/.config/avream/avreamd.env
ExecStart=$VENV_DIR/bin/avreamd
Restart=on-failure
RestartSec=2
NoNewPrivileges=true

[Install]
WantedBy=default.target
EOF

if [ ! -f "$ENV_FILE" ]; then
  cat > "$ENV_FILE" <<EOF
# Environment overrides for avreamd
# AVREAM_SOCKET_PATH=
# AVREAM_LOG_LEVEL=DEBUG
EOF
fi

systemctl --user daemon-reload
systemctl --user enable --now avreamd.service

echo "Installed user service: $SERVICE_PATH"
systemctl --user --no-pager status avreamd.service || true
