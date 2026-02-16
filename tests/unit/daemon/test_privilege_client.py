from __future__ import annotations

import unittest
from unittest.mock import patch

from avreamd.api.errors import ApiError
from avreamd.managers.privilege_client import PrivilegeClient


class _ProcStub:
    def __init__(self, *, returncode: int, stdout: bytes = b"", stderr: bytes = b"") -> None:
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self, _payload: bytes) -> tuple[bytes, bytes]:
        return self._stdout, self._stderr


class PrivilegeClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_allowlisted_action(self) -> None:
        client = PrivilegeClient(helper_bin="/usr/libexec/avream-helper")
        with self.assertRaises(ApiError) as ctx:
            await client.call("rm -rf", {})
        self.assertEqual(ctx.exception.code, "E_UNSUPPORTED")

    async def test_rejects_relative_helper_path(self) -> None:
        client = PrivilegeClient(helper_bin="avream-helper")
        with self.assertRaises(ApiError) as ctx:
            await client.call("noop", {})
        self.assertEqual(ctx.exception.code, "E_PERMISSION")

    async def test_maps_pkexec_denied_to_permission_error(self) -> None:
        client = PrivilegeClient(helper_bin="/usr/libexec/avream-helper")
        with patch("asyncio.create_subprocess_exec", return_value=_ProcStub(returncode=126, stderr=b"Authentication failed")):
            with self.assertRaises(ApiError) as ctx:
                await client.call("noop", {})
        self.assertEqual(ctx.exception.code, "E_PERMISSION")
        self.assertIn("hint", (ctx.exception.details or {}))

    async def test_pkexec_setuid_error_falls_back_to_systemd_run(self) -> None:
        client = PrivilegeClient(helper_bin="/usr/libexec/avream-helper")
        client.mode = "auto"
        procs = [
            _ProcStub(returncode=127, stderr=b"pkexec must be setuid root"),
            _ProcStub(returncode=0, stdout=b'{"ok": true, "data": {"reloaded": true}}'),
        ]

        with patch("asyncio.create_subprocess_exec", side_effect=procs) as create_proc:
            with patch.object(client, "_pkexec_usable", return_value=True):
                with patch("shutil.which", return_value="/usr/bin/systemd-run"):
                    data = await client.call(
                        "v4l2.reload",
                        {"video_nr": 10, "label": "AVream Camera", "exclusive_caps": True},
                    )

        self.assertTrue(data.get("reloaded"))
        self.assertEqual(create_proc.call_count, 2)


if __name__ == "__main__":
    unittest.main()
