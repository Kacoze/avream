#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${1:-$ROOT_DIR/dist}"
OUT_DIR="${2:-$ROOT_DIR/dist/apt}"
SUITE="${AVREAM_APT_SUITE:-stable}"
COMPONENT="${AVREAM_APT_COMPONENT:-main}"
ARCH="${AVREAM_DEB_ARCH:-amd64}"

if ! command -v apt-ftparchive >/dev/null 2>&1; then
  echo "apt-ftparchive is required (install apt-utils)." >&2
  exit 1
fi

mkdir -p "$OUT_DIR/pool/$COMPONENT"
mkdir -p "$OUT_DIR/dists/$SUITE/$COMPONENT/binary-$ARCH"

shopt -s nullglob
deb_files=("$DIST_DIR"/*.deb)
if [ "${#deb_files[@]}" -eq 0 ]; then
  echo "No .deb files found in $DIST_DIR" >&2
  exit 1
fi

cp "${deb_files[@]}" "$OUT_DIR/pool/$COMPONENT/"

packages_path="$OUT_DIR/dists/$SUITE/$COMPONENT/binary-$ARCH/Packages"
apt-ftparchive packages "$OUT_DIR/pool/$COMPONENT" > "$packages_path"
gzip -9c "$packages_path" > "${packages_path}.gz"

release_path="$OUT_DIR/dists/$SUITE/Release"
apt-ftparchive \
  -o "APT::FTPArchive::Release::Origin=AVream" \
  -o "APT::FTPArchive::Release::Label=AVream" \
  -o "APT::FTPArchive::Release::Suite=$SUITE" \
  -o "APT::FTPArchive::Release::Codename=$SUITE" \
  -o "APT::FTPArchive::Release::Architectures=$ARCH" \
  -o "APT::FTPArchive::Release::Components=$COMPONENT" \
  release "$OUT_DIR/dists/$SUITE" > "$release_path"

echo "Built APT repository structure in $OUT_DIR"
