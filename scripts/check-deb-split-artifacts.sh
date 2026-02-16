#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <dist-dir> <version>" >&2
  exit 1
fi

dist_dir="$1"
version="$2"
arch="amd64"

required=(
  "avream-meta_${version}_${arch}.deb"
  "avream-daemon_${version}_${arch}.deb"
  "avream-ui_${version}_${arch}.deb"
  "avream-helper_${version}_${arch}.deb"
)

for pkg in "${required[@]}"; do
  if [ ! -f "$dist_dir/$pkg" ]; then
    echo "Missing split package: $dist_dir/$pkg" >&2
    exit 1
  fi
done

tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT

dpkg-deb -x "$dist_dir/avream-daemon_${version}_${arch}.deb" "$tmpdir/daemon"
dpkg-deb -x "$dist_dir/avream-ui_${version}_${arch}.deb" "$tmpdir/ui"
dpkg-deb -x "$dist_dir/avream-helper_${version}_${arch}.deb" "$tmpdir/helper"

test -f "$tmpdir/daemon/usr/bin/avreamd"
test -f "$tmpdir/daemon/usr/bin/avream"
test -f "$tmpdir/ui/usr/bin/avream-ui"
test -f "$tmpdir/helper/usr/libexec/avream-helper"
test -f "$tmpdir/helper/usr/bin/avream-passwordless-setup"

echo "Split Debian artifact check passed"
