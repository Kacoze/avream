#!/usr/bin/env bash
set -euo pipefail

DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

bash "$DIR/dev-install-user-service.sh"
bash "$DIR/dev-install-helper.sh"

echo "Done. Try: curl --unix-socket \"$XDG_RUNTIME_DIR/avream/daemon.sock\" http://localhost/status"
