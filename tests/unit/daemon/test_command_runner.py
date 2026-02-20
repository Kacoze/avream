from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
from avreamd.integrations.command_runner import CommandRunner


class CommandRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_async(self) -> None:
        runner = CommandRunner()
        result = await runner.run_async(["bash", "-lc", "printf ok"])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "ok")

    async def test_run_sync(self) -> None:
        runner = CommandRunner()
        result = runner.run_sync(["bash", "-lc", "printf sync"])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "sync")


if __name__ == "__main__":
    unittest.main()
