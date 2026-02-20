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

ARCH=${AVREAM_RPM_ARCH:-"x86_64"}
OUT_DIR=${AVREAM_RPM_OUT_DIR:-"$ROOT_DIR/dist"}

mkdir -p "$OUT_DIR"
bash "$ROOT_DIR/scripts/generate-dist-docs.sh"

if ! command -v rpmbuild >/dev/null 2>&1; then
  echo "Error: rpmbuild is required" >&2
  exit 1
fi

if ! command -v cargo >/dev/null 2>&1; then
  echo "Error: cargo is required to build helper" >&2
  exit 1
fi

(cd "$ROOT_DIR/helper" && cargo build --release)

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

TOPDIR="$tmp/rpmbuild"
mkdir -p "$TOPDIR"/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
SPEC_FILE="$TOPDIR/SPECS/avream.spec"

cat > "$SPEC_FILE" <<SPEC
Name:           avream
Version:        ${VERSION}
Release:        1
Summary:        AVream daemon, GUI, and privileged helper
License:        MIT
URL:            https://github.com/Kacoze/avream
BuildArch:      ${ARCH}
Requires:       python3

%description
AVream provides a user daemon managing virtual A/V devices,
a GTK/libadwaita GUI, and a privileged helper invoked via polkit.

%prep

%build

%install
rm -rf %{buildroot}

install -D -m 0644 ${ROOT_DIR}/packaging/systemd/user/avreamd.service %{buildroot}%{_prefix}/lib/systemd/user/avreamd.service
install -D -m 0644 ${ROOT_DIR}/packaging/systemd/user/avreamd.env %{buildroot}%{_prefix}/lib/systemd/user/avreamd.env
install -D -m 0644 ${ROOT_DIR}/packaging/polkit/io.avream.helper.policy %{buildroot}%{_datadir}/polkit-1/actions/io.avream.helper.policy
install -D -m 0644 ${ROOT_DIR}/packaging/desktop/io.avream.AVream.desktop %{buildroot}%{_datadir}/applications/io.avream.AVream.desktop
install -D -m 0644 ${ROOT_DIR}/packaging/desktop/io.avream.AVream.appdata.xml %{buildroot}%{_datadir}/metainfo/io.avream.AVream.appdata.xml
install -D -m 0644 ${ROOT_DIR}/packaging/desktop/io.avream.AVream.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/io.avream.AVream.svg
install -D -m 0644 ${ROOT_DIR}/dist/README_USER.md %{buildroot}%{_datadir}/doc/avream/README_USER.md
install -D -m 0644 ${ROOT_DIR}/dist/CLI_README.md %{buildroot}%{_datadir}/doc/avream/CLI_README.md
install -D -m 0755 ${ROOT_DIR}/helper/target/release/avream-helper %{buildroot}%{_libexecdir}/avream-helper
install -D -m 0755 ${ROOT_DIR}/scripts/avream-passwordless-setup.sh %{buildroot}%{_bindir}/avream-passwordless-setup

mkdir -p %{buildroot}%{_prefix}/lib/avream/python
tar -C ${ROOT_DIR}/src --exclude='__pycache__' --exclude='*.pyc' -cf - avreamd | tar -C %{buildroot}%{_prefix}/lib/avream/python -xf -
tar -C ${ROOT_DIR}/ui/src --exclude='__pycache__' --exclude='*.pyc' -cf - avream_ui | tar -C %{buildroot}%{_prefix}/lib/avream/python -xf -

cat > %{buildroot}%{_bindir}/avreamd <<'PYEOF'
#!/usr/bin/python3
import sys
sys.path.insert(0, "/usr/lib/avream/python")
from avreamd.main import main
raise SystemExit(main())
PYEOF
chmod 0755 %{buildroot}%{_bindir}/avreamd

cat > %{buildroot}%{_bindir}/avream <<'PYEOF'
#!/usr/bin/python3
import sys
sys.path.insert(0, "/usr/lib/avream/python")
from avreamd.cli import main
raise SystemExit(main())
PYEOF
chmod 0755 %{buildroot}%{_bindir}/avream

cat > %{buildroot}%{_bindir}/avream-ui <<'PYEOF'
#!/usr/bin/python3
import sys
sys.path.insert(0, "/usr/lib/avream/python")
from avream_ui.main import main
raise SystemExit(main())
PYEOF
chmod 0755 %{buildroot}%{_bindir}/avream-ui

%files
%{_bindir}/avream
%{_bindir}/avreamd
%{_bindir}/avream-ui
%{_bindir}/avream-passwordless-setup
%{_libexecdir}/avream-helper
%{_prefix}/lib/systemd/user/avreamd.service
%{_prefix}/lib/systemd/user/avreamd.env
%{_datadir}/polkit-1/actions/io.avream.helper.policy
%{_datadir}/applications/io.avream.AVream.desktop
%{_datadir}/metainfo/io.avream.AVream.appdata.xml
%{_datadir}/icons/hicolor/scalable/apps/io.avream.AVream.svg
%{_datadir}/doc/avream/README_USER.md
%{_datadir}/doc/avream/CLI_README.md
%{_prefix}/lib/avream/python/avreamd
%{_prefix}/lib/avream/python/avream_ui

%changelog
* Fri Feb 20 2026 AVream contributors <noreply@avream.io> - ${VERSION}-1
- Automated RPM build
SPEC

rpmbuild --define "_topdir ${TOPDIR}" -bb "$SPEC_FILE" >/dev/null

rpm_path=$(find "$TOPDIR/RPMS" -type f -name "avream-${VERSION}-1*.rpm" | head -n1 || true)
if [ -z "$rpm_path" ]; then
  echo "Error: built RPM not found" >&2
  exit 1
fi

cp "$rpm_path" "$OUT_DIR/"
echo "Built: $OUT_DIR/$(basename "$rpm_path")"
