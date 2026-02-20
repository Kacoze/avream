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
trap 'rm -rf "$tmp"' EXIT

build_pkg() {
  local name="$1"
  local depends="$2"
  local recommends="$3"
  local description="$4"
  local replaces=""
  local conflicts=""
  local pkgdir="$tmp/${name}_${VERSION}_${ARCH}"

  case "$name" in
    avream-daemon|avream-ui|avream-helper)
      replaces="avream"
      conflicts="avream"
      ;;
  esac

  mkdir -p "$pkgdir/DEBIAN"
  cat > "$pkgdir/DEBIAN/control" <<EOF
Package: $name
Version: $VERSION
Section: video
Priority: optional
Architecture: $ARCH
Maintainer: AVream contributors
Depends: $depends
Recommends: $recommends
Description: $description
EOF

  if [ -n "$replaces" ]; then
    printf 'Replaces: %s\n' "$replaces" >> "$pkgdir/DEBIAN/control"
  fi
  if [ -n "$conflicts" ]; then
    printf 'Conflicts: %s\n' "$conflicts" >> "$pkgdir/DEBIAN/control"
  fi

  case "$name" in
    avream-daemon)
      install -D -m 0644 "$ROOT_DIR/packaging/systemd/user/avreamd.service" "$pkgdir/usr/lib/systemd/user/avreamd.service"
      install -D -m 0644 "$ROOT_DIR/packaging/systemd/user/avreamd.env" "$pkgdir/usr/lib/systemd/user/avreamd.env"
      install -D -m 0755 "$ROOT_DIR/packaging/debian/postinst" "$pkgdir/DEBIAN/postinst"
      install -D -m 0755 "$ROOT_DIR/packaging/debian/prerm" "$pkgdir/DEBIAN/prerm"
      mkdir -p "$pkgdir/usr/lib/python3/dist-packages"
      tar -C "$ROOT_DIR/src" --exclude='__pycache__' --exclude='*.pyc' -cf - avreamd | tar -C "$pkgdir/usr/lib/python3/dist-packages" -xf -
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
      ;;
    avream-ui)
      install -D -m 0644 "$ROOT_DIR/packaging/desktop/io.avream.AVream.desktop" "$pkgdir/usr/share/applications/io.avream.AVream.desktop"
      install -D -m 0644 "$ROOT_DIR/packaging/desktop/io.avream.AVream.appdata.xml" "$pkgdir/usr/share/metainfo/io.avream.AVream.appdata.xml"
      install -D -m 0644 "$ROOT_DIR/packaging/desktop/io.avream.AVream.svg" "$pkgdir/usr/share/icons/hicolor/scalable/apps/io.avream.AVream.svg"
      install -D -m 0644 "$ROOT_DIR/dist/README_USER.md" "$pkgdir/usr/share/doc/avream/README_USER.md"
      install -D -m 0644 "$ROOT_DIR/dist/CLI_README.md" "$pkgdir/usr/share/doc/avream/CLI_README.md"
      mkdir -p "$pkgdir/usr/lib/python3/dist-packages"
      tar -C "$ROOT_DIR/ui/src" --exclude='__pycache__' --exclude='*.pyc' -cf - avream_ui | tar -C "$pkgdir/usr/lib/python3/dist-packages" -xf -
      install -D -m 0755 /dev/stdin "$pkgdir/usr/bin/avream-ui" <<'EOF'
#!/usr/bin/python3
from avream_ui.main import main

raise SystemExit(main())
EOF
      ;;
    avream-helper)
      install -D -m 0644 "$ROOT_DIR/packaging/polkit/io.avream.helper.policy" "$pkgdir/usr/share/polkit-1/actions/io.avream.helper.policy"
      install -D -m 0755 "$ROOT_DIR/helper/target/release/avream-helper" "$pkgdir/usr/libexec/avream-helper"
      install -D -m 0755 "$ROOT_DIR/scripts/avream-passwordless-setup.sh" "$pkgdir/usr/bin/avream-passwordless-setup"
      ;;
    avream-meta)
      ;;
  esac

  dpkg-deb --build --root-owner-group "$pkgdir" "$OUT_DIR/${name}_${VERSION}_${ARCH}.deb" >/dev/null
}

build_pkg "avream-daemon" "python3 (>= 3.10), python3-aiohttp, systemd" "scrcpy, android-tools-adb, pipewire, pipewire-pulse" "AVream user daemon and API service"
build_pkg "avream-ui" "python3 (>= 3.10), python3-aiohttp, python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1" "avream-daemon" "AVream GTK desktop application"
build_pkg "avream-helper" "polkitd, policykit-1, kmod, psmisc" "" "AVream privileged helper and polkit policy"
build_pkg "avream-meta" "avream-daemon (= $VERSION), avream-ui (= $VERSION), avream-helper (= $VERSION)" "" "AVream transitional meta package"

echo "Built split packages in $OUT_DIR"
