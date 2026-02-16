#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <path-to-deb>" >&2
  exit 1
fi

deb_path="$1"
if [ ! -f "$deb_path" ]; then
  echo "Error: package not found: $deb_path" >&2
  exit 1
fi

tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT

dpkg-deb -x "$deb_path" "$tmpdir/root"
dpkg-deb -e "$deb_path" "$tmpdir/control"

python3 - "$tmpdir/root" "$tmpdir/control" <<'PY'
from __future__ import annotations

import pathlib
import sys

root = pathlib.Path(sys.argv[1])
control = pathlib.Path(sys.argv[2])

required_root = [
    "usr/bin/avream",
    "usr/bin/avreamd",
    "usr/bin/avream-ui",
    "usr/bin/avream-passwordless-setup",
    "usr/libexec/avream-helper",
    "usr/lib/systemd/user/avreamd.service",
    "usr/lib/systemd/user/avreamd.env",
    "usr/share/polkit-1/actions/io.avream.helper.policy",
    "usr/share/applications/io.avream.AVream.desktop",
    "usr/share/metainfo/io.avream.AVream.appdata.xml",
    "usr/share/icons/hicolor/scalable/apps/io.avream.AVream.svg",
    "usr/lib/python3/dist-packages/avreamd/main.py",
    "usr/lib/python3/dist-packages/avream_ui/main.py",
]
required_control = ["control", "postinst", "prerm"]

missing = [p for p in required_root if not (root / p).exists()]
missing.extend([f"DEBIAN/{p}" for p in required_control if not (control / p).exists()])
if missing:
    raise SystemExit(f"Missing package entries: {', '.join(missing)}")

for script in (control / "postinst", control / "prerm"):
    mode = script.stat().st_mode
    if mode & 0o111 == 0:
        raise SystemExit(f"Maintainer script is not executable: {script.name}")

for launcher in (root / "usr/bin/avream", root / "usr/bin/avreamd", root / "usr/bin/avream-ui"):
    text = launcher.read_text(encoding="utf-8")
    if "#!/usr/bin/python3" not in text:
        raise SystemExit(f"Unexpected launcher shebang in {launcher}")

print("Debian artifact sanity check passed")
PY

python3 -m py_compile \
  "$tmpdir/root/usr/lib/python3/dist-packages/avreamd/cli.py" \
  "$tmpdir/root/usr/lib/python3/dist-packages/avreamd/main.py" \
  "$tmpdir/root/usr/lib/python3/dist-packages/avream_ui/main.py"

echo "Validated package: $deb_path"
