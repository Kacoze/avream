from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from avreamd.api.errors import ApiError
from avreamd.managers.update.checksum_verifier import ChecksumVerifier


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ChecksumVerifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self._root = Path(self._td.name)
        self._verifier = ChecksumVerifier()
        self._asset_name = "avream_9.9.9_amd64.deb"
        self._deb_path = self._root / self._asset_name
        self._sums_path = self._root / "SHA256SUMS.txt"
        self._content = b"fake deb content"
        self._deb_path.write_bytes(self._content)

    def tearDown(self) -> None:
        self._td.cleanup()

    def _write_sums(self, text: str) -> None:
        self._sums_path.write_text(text, encoding="utf-8")

    def test_verify_passes_on_matching_hash(self) -> None:
        digest = _sha256(self._content)
        self._write_sums(f"{digest}  {self._asset_name}\n")
        # Should not raise
        self._verifier.verify_checksum(
            asset_name=self._asset_name,
            deb_path=self._deb_path,
            sums_path=self._sums_path,
        )

    def test_verify_passes_with_single_space_separator(self) -> None:
        digest = _sha256(self._content)
        self._write_sums(f"{digest} {self._asset_name}\n")
        self._verifier.verify_checksum(
            asset_name=self._asset_name,
            deb_path=self._deb_path,
            sums_path=self._sums_path,
        )

    def test_verify_passes_with_uppercase_hash(self) -> None:
        digest = _sha256(self._content).upper()
        self._write_sums(f"{digest}  {self._asset_name}\n")
        self._verifier.verify_checksum(
            asset_name=self._asset_name,
            deb_path=self._deb_path,
            sums_path=self._sums_path,
        )

    def test_verify_raises_on_mismatch(self) -> None:
        wrong_digest = "0" * 64
        self._write_sums(f"{wrong_digest}  {self._asset_name}\n")
        with self.assertRaises(ApiError) as ctx:
            self._verifier.verify_checksum(
                asset_name=self._asset_name,
                deb_path=self._deb_path,
                sums_path=self._sums_path,
            )
        self.assertIn("mismatch", ctx.exception.message)

    def test_verify_raises_when_entry_missing(self) -> None:
        digest = _sha256(self._content)
        self._write_sums(f"{digest}  other_package_1.0.deb\n")
        with self.assertRaises(ApiError) as ctx:
            self._verifier.verify_checksum(
                asset_name=self._asset_name,
                deb_path=self._deb_path,
                sums_path=self._sums_path,
            )
        self.assertIn("not found", ctx.exception.message)

    def test_verify_raises_on_empty_sums_file(self) -> None:
        self._write_sums("")
        with self.assertRaises(ApiError):
            self._verifier.verify_checksum(
                asset_name=self._asset_name,
                deb_path=self._deb_path,
                sums_path=self._sums_path,
            )

    def test_verify_handles_multiple_entries_picks_correct_one(self) -> None:
        digest = _sha256(self._content)
        self._write_sums(
            f"{'a' * 64}  other_package.deb\n"
            f"{digest}  {self._asset_name}\n"
            f"{'b' * 64}  yet_another.deb\n"
        )
        self._verifier.verify_checksum(
            asset_name=self._asset_name,
            deb_path=self._deb_path,
            sums_path=self._sums_path,
        )


if __name__ == "__main__":
    unittest.main()
