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

    def test_debian_derivatives_are_compatible(self) -> None:
        self.assertEqual(self._detect("linuxmint-22"), ("compatible", "debian", "linuxmint"))
        self.assertEqual(self._detect("pop-24.04"), ("compatible", "debian", "pop"))
        self.assertEqual(self._detect("zorin-17"), ("compatible", "debian", "zorin"))

    def test_id_like_debian_is_compatible(self) -> None:
        self.assertEqual(self._detect("custom-debian-like"), ("compatible", "debian", "mydebianclone"))

    def test_rpm_family_detection(self) -> None:
        self.assertEqual(self._detect("fedora-41"), ("official", "rpm", "fedora"))
        self.assertEqual(self._detect("opensuse-tumbleweed"), ("compatible", "rpm", "opensuse-tumbleweed"))

    def test_arch_and_nix_detection(self) -> None:
        self.assertEqual(self._detect("arch"), ("compatible", "arch", "arch"))
        self.assertEqual(self._detect("nixos"), ("compatible", "nix", "nixos"))


class InstallMethodResolutionTests(unittest.TestCase):
    def _resolve(self, method: str, backend: str) -> tuple[int, str]:
        cmd = (
            "source scripts/lib/install-platform.sh; "
            "avream_resolve_install_method \"$1\" \"$2\"; "
            "printf '%s|%s' \"$AVREAM_INSTALL_PRIMARY\" \"$AVREAM_INSTALL_FALLBACK\""
        )
        result = subprocess.run(
            ["bash", "-lc", cmd, "--", method, backend],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        return result.returncode, result.stdout.strip()

    def test_auto_uses_repo_with_release_fallback_for_apt(self) -> None:
        code, out = self._resolve("auto", "apt")
        self.assertEqual(code, 0)
        self.assertEqual(out, "repo|release")

    def test_auto_uses_release_for_rpm(self) -> None:
        for backend in ("dnf", "zypper"):
            code, out = self._resolve("auto", backend)
            self.assertEqual((code, out), (0, "release|"))

    def test_auto_uses_arch_and_nix_paths_when_needed(self) -> None:
        arch_code, arch_out = self._resolve("auto", "pacman")
        nix_code, nix_out = self._resolve("auto", "nix")
        self.assertEqual((arch_code, arch_out), (0, "aur|"))
        self.assertEqual((nix_code, nix_out), (0, "nix|"))

    def test_explicit_methods_have_no_fallback(self) -> None:
        repo_code, repo_out = self._resolve("repo", "apt")
        rel_code, rel_out = self._resolve("release", "apt")
        self.assertEqual((repo_code, repo_out), (0, "repo|"))
        self.assertEqual((rel_code, rel_out), (0, "release|"))

    def test_invalid_method_fails(self) -> None:
        code, out = self._resolve("invalid", "apt")
        self.assertNotEqual(code, 0)
        self.assertEqual(out, "")

    def test_unknown_backend_in_auto_fails(self) -> None:
        code, out = self._resolve("auto", "unknown")
        self.assertNotEqual(code, 0)
        self.assertEqual(out, "")


if __name__ == "__main__":
    unittest.main()
