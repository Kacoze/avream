#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <dist-dir> <version>" >&2
  exit 1
fi

dist_dir="$1"
version="$2"
image="ubuntu:24.04"

if [ ! -d "$dist_dir" ]; then
  echo "Error: dist directory not found: $dist_dir" >&2
  exit 1
fi

dist_dir_abs=$(realpath "$dist_dir")

docker run --rm -v "$dist_dir_abs:/dist" "$image" bash -lc "
  set -euo pipefail
  apt-get update
  apt-get install -y ca-certificates curl

  # Baseline: monolithic package.
  apt-get install -y /dist/avream_${version}_amd64.deb
  avreamd --help
  avream-ui --help

  # Upgrade path: split package set.
  apt-get install -y \
    /dist/avream-daemon_${version}_amd64.deb \
    /dist/avream-ui_${version}_amd64.deb \
    /dist/avream-helper_${version}_amd64.deb
  avreamd --help
  avream-ui --help
"

echo "Split upgrade test passed for version $version"
