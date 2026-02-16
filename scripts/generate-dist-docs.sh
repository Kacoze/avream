#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
OUT_DIR=${AVREAM_DEB_OUT_DIR:-"$ROOT_DIR/dist"}

mkdir -p "$OUT_DIR"

cp "$ROOT_DIR/docs/USER_GUIDE.md" "$OUT_DIR/README_USER.md"
cp "$ROOT_DIR/docs/API_V1.md" "$OUT_DIR/API_MINIMAL.md"
cp "$ROOT_DIR/docs/CLI_README.md" "$OUT_DIR/CLI_README.md"

cat > "$OUT_DIR/UPGRADE_NOTES.md" <<'EOF'
# AVream Upgrade Notes (Phone-first)

This release simplifies AVream to a phone-first product.

## Main changes

- Product focus is now Android phone as camera and/or microphone.
- Public API removed endpoints for sources, profiles, doctor, fix, and logs.
- UI now focuses on phone actions and camera/microphone controls.

## Removed API endpoints

- `/sources/*`
- `/profiles/*`
- `/doctor/*`
- `/fix/*`
- `/logs/*`
- `/video/reconnect/stop`

## Runtime impact

- Existing source/profile data files may remain on disk but are no longer used by the default flow.
- If you integrated with removed endpoints, migrate to the phone-first endpoints in `API_MINIMAL.md`.
EOF

echo "Generated dist docs in $OUT_DIR"
