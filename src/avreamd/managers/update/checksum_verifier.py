from __future__ import annotations

import hashlib
from pathlib import Path

from avreamd.api.errors import backend_error


class ChecksumVerifier:
    def verify_checksum(self, *, asset_name: str, deb_path: Path, sums_path: Path) -> None:
        sums_text = sums_path.read_text(encoding="utf-8", errors="replace")
        expected = None
        for line in sums_text.splitlines():
            parts = line.strip().split()
            if len(parts) >= 2 and parts[-1].endswith(asset_name):
                expected = parts[0]
                break
        if not expected:
            raise backend_error("checksum entry for asset not found", {"asset": asset_name})

        digest = hashlib.sha256(deb_path.read_bytes()).hexdigest()
        if digest.lower() != expected.lower():
            raise backend_error(
                "checksum mismatch",
                {"asset": asset_name, "expected": expected, "actual": digest},
                retryable=False,
            )
