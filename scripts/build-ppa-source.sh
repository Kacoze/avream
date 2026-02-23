#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION_FILE="${ROOT_DIR}/src/avreamd/VERSION"

if [ -n "${AVREAM_VERSION:-}" ]; then
  VERSION="${AVREAM_VERSION}"
elif [ -f "${VERSION_FILE}" ]; then
  VERSION="$(tr -d '[:space:]' < "${VERSION_FILE}")"
else
  VERSION="0.0.0"
fi

PPA_REVISION="${AVREAM_PPA_REVISION:-1}"
DISTRO="${AVREAM_PPA_DISTRIBUTION:-jammy}"
OUT_DIR="${AVREAM_PPA_OUT_DIR:-${ROOT_DIR}/dist/ppa}"
DEB_VERSION="${VERSION}+ppa${PPA_REVISION}"

mkdir -p "${OUT_DIR}"
tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

src_dir="${tmp}/avream-${VERSION}"
mkdir -p "${src_dir}"

git -C "${ROOT_DIR}" archive --format=tar HEAD | tar -xf - -C "${src_dir}"

cat > "${src_dir}/debian/changelog" <<EOF
avream (${DEB_VERSION}) ${DISTRO}; urgency=medium

  * Automated PPA source package build.

 -- AVream contributors <noreply@avream.io>  $(date -R)
EOF

build_flags=(-S -sa)
if [ -z "${AVREAM_PPA_GPG_KEYID:-}" ]; then
  build_flags+=(-us -uc)
fi

(
  cd "${src_dir}"
  dpkg-buildpackage "${build_flags[@]}"
)

find "${tmp}" -maxdepth 1 -type f \
  \( -name "*.dsc" -o -name "*.changes" -o -name "*.buildinfo" -o -name "*.tar.*" \) \
  -exec cp {} "${OUT_DIR}/" \;

echo "Built PPA source artifacts in ${OUT_DIR}"
