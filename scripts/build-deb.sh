#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
VERSION_FILE="$ROOT_DIR/src/avreamd/VERSION"

if [ -n "${AVREAM_VERSION:-}" ]; then
  VERSION="$AVREAM_VERSION"
elif [ -f "$VERSION_FILE" ]; then
  VERSION=$(tr -d '[:space:]' < "$VERSION_FILE")
else
  VERSION="0.0.0~dev"
fi
ARCH=${AVREAM_DEB_ARCH:-"amd64"}
OUT_DIR=${AVREAM_DEB_OUT_DIR:-"$ROOT_DIR/dist"}

mkdir -p "$OUT_DIR"
bash "$ROOT_DIR/scripts/generate-dist-docs.sh"

if ! command -v dpkg-deb >/dev/null 2>&1; then
  echo "Error: dpkg-deb is required" >&2
  exit 1
fi

if ! command -v cargo >/dev/null 2>&1; then
  echo "Error: cargo is required to build helper" >&2
  exit 1
fi

(cd "$ROOT_DIR/helper" && cargo build --release)

tmp=$(mktemp -d)
pkgdir="$tmp/avream_${VERSION}_${ARCH}"
mkdir -p "$pkgdir/DEBIAN"

cat > "$pkgdir/DEBIAN/control" <<EOF
Package: avream
Version: $VERSION
Section: video
Priority: optional
Architecture: $ARCH
Maintainer: AVream contributors
Depends: python3 (>= 3.10), python3-aiohttp, python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1, polkitd, policykit-1, kmod, psmisc
Recommends: scrcpy, android-tools-adb, pipewire, pipewire-pulse
Description: AVream daemon, GUI, and privileged helper
 AVream provides a user daemon managing virtual A/V devices,
 a GTK/libadwaita GUI, and a privileged helper invoked via polkit.
EOF

install -D -m 0755 "$ROOT_DIR/packaging/debian/postinst" "$pkgdir/DEBIAN/postinst"
install -D -m 0755 "$ROOT_DIR/packaging/debian/prerm" "$pkgdir/DEBIAN/prerm"

# Files
install -D -m 0644 "$ROOT_DIR/packaging/systemd/user/avreamd.service" "$pkgdir/usr/lib/systemd/user/avreamd.service"
install -D -m 0644 "$ROOT_DIR/packaging/systemd/user/avreamd.env" "$pkgdir/usr/lib/systemd/user/avreamd.env"
install -D -m 0644 "$ROOT_DIR/packaging/polkit/io.avream.helper.policy" "$pkgdir/usr/share/polkit-1/actions/io.avream.helper.policy"
install -D -m 0644 "$ROOT_DIR/packaging/desktop/io.avream.AVream.desktop" "$pkgdir/usr/share/applications/io.avream.AVream.desktop"
install -D -m 0644 "$ROOT_DIR/packaging/desktop/io.avream.AVream.appdata.xml" "$pkgdir/usr/share/metainfo/io.avream.AVream.appdata.xml"
install -D -m 0644 "$ROOT_DIR/packaging/desktop/io.avream.AVream.svg" "$pkgdir/usr/share/icons/hicolor/scalable/apps/io.avream.AVream.svg"
install -D -m 0644 "$ROOT_DIR/dist/README_USER.md" "$pkgdir/usr/share/doc/avream/README_USER.md"
install -D -m 0644 "$ROOT_DIR/dist/CLI_README.md" "$pkgdir/usr/share/doc/avream/CLI_README.md"
install -D -m 0755 "$ROOT_DIR/helper/target/release/avream-helper" "$pkgdir/usr/libexec/avream-helper"
install -D -m 0755 "$ROOT_DIR/scripts/avream-passwordless-setup.sh" "$pkgdir/usr/bin/avream-passwordless-setup"

mkdir -p "$pkgdir/usr/lib/python3/dist-packages"
tar -C "$ROOT_DIR/src" --exclude='__pycache__' --exclude='*.pyc' -cf - avreamd | tar -C "$pkgdir/usr/lib/python3/dist-packages" -xf -
tar -C "$ROOT_DIR/ui/src" --exclude='__pycache__' --exclude='*.pyc' -cf - avream_ui | tar -C "$pkgdir/usr/lib/python3/dist-packages" -xf -

install -D -m 0755 /dev/stdin "$pkgdir/usr/bin/avreamd" <<'EOF'
#!/usr/bin/python3
from avreamd.main import main

raise SystemExit(main())
EOF

install -D -m 0755 /dev/stdin "$pkgdir/usr/bin/avream" <<'EOF'
#!/usr/bin/python3
from avreamd.cli import main

raise SystemExit(main())
EOF

install -D -m 0755 /dev/stdin "$pkgdir/usr/bin/avream-ui" <<'EOF'
#!/usr/bin/python3
from avream_ui.main import main

raise SystemExit(main())
EOF

dpkg-deb --build --root-owner-group "$pkgdir" "$OUT_DIR/avream_${VERSION}_${ARCH}.deb" >/dev/null

rm -rf "$tmp"
echo "Built: $OUT_DIR/avream_${VERSION}_${ARCH}.deb"
