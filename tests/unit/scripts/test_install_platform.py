from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests" / "fixtures" / "install" / "os-release"


class InstallPlatformDetectionTests(unittest.TestCase):
    def _detect(self, fixture_name: str) -> tuple[str, str, str]:
        fixture = FIXTURES / fixture_name
        cmd = (
            "source scripts/lib/install-platform.sh; "
            "avream_detect_platform_support \"$1\"; "
            "printf '%s|%s|%s' \"$AVREAM_PLATFORM_STATUS\" \"$AVREAM_PLATFORM_FAMILY\" \"$AVREAM_OS_ID\""
        )
        result = subprocess.run(
            ["bash", "-lc", cmd, "--", str(fixture)],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        return tuple(result.stdout.strip().split("|"))  # type: ignore[return-value]

    def test_debian_and_ubuntu_are_official(self) -> None:
        self.assertEqual(self._detect("debian-13"), ("official", "debian", "debian"))
        self.assertEqual(self._detect("ubuntu-24.04"), ("official", "debian", "ubuntu"))

    def test_derivatives_are_compatible(self) -> None:
        self.assertEqual(self._detect("linuxmint-22"), ("compatible", "debian", "linuxmint"))
        self.assertEqual(self._detect("pop-24.04"), ("compatible", "debian", "pop"))
        self.assertEqual(self._detect("zorin-17"), ("compatible", "debian", "zorin"))

    def test_id_like_debian_is_compatible(self) -> None:
        self.assertEqual(self._detect("custom-debian-like"), ("compatible", "debian", "mydebianclone"))

    def test_non_debian_family_is_unsupported(self) -> None:
        self.assertEqual(self._detect("fedora-41"), ("unsupported", "unknown", "fedora"))


class InstallMethodResolutionTests(unittest.TestCase):
    def _resolve(self, method: str) -> tuple[int, str]:
        cmd = (
            "source scripts/lib/install-platform.sh; "
            "avream_resolve_install_method \"$1\"; "
            "printf '%s|%s' \"$AVREAM_INSTALL_PRIMARY\" \"$AVREAM_INSTALL_FALLBACK\""
        )
        result = subprocess.run(
            ["bash", "-lc", cmd, "--", method],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        return result.returncode, result.stdout.strip()

    def test_auto_uses_repo_with_release_fallback(self) -> None:
        code, out = self._resolve("auto")
        self.assertEqual(code, 0)
        self.assertEqual(out, "repo|release")

    def test_explicit_methods_have_no_fallback(self) -> None:
        repo_code, repo_out = self._resolve("repo")
        rel_code, rel_out = self._resolve("release")
        self.assertEqual((repo_code, repo_out), (0, "repo|"))
        self.assertEqual((rel_code, rel_out), (0, "release|"))

    def test_invalid_method_fails(self) -> None:
        code, out = self._resolve("invalid")
        self.assertNotEqual(code, 0)
        self.assertEqual(out, "")


if __name__ == "__main__":
    unittest.main()
