from __future__ import annotations

import asyncio
import unittest

from avreamd.core.state_store import DaemonStateStore, InvalidTransitionError, SubsystemState


class StateStoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_initial_state_is_stopped(self) -> None:
        store = DaemonStateStore()
        snapshot = await store.snapshot()
        self.assertEqual(snapshot["video"]["state"], "STOPPED")
        self.assertEqual(snapshot["audio"]["state"], "STOPPED")

    async def test_valid_video_transition_sequence(self) -> None:
        store = DaemonStateStore()
        await store.transition_video(SubsystemState.STARTING)
        await store.transition_video(SubsystemState.RUNNING)
        await store.transition_video(SubsystemState.STOPPING)
        await store.transition_video(SubsystemState.STOPPED)
        snapshot = await store.snapshot()
        self.assertEqual(snapshot["video"]["state"], "STOPPED")

    async def test_invalid_video_transition_raises(self) -> None:
        store = DaemonStateStore()
        with self.assertRaises(InvalidTransitionError):
            await store.transition_video(SubsystemState.RUNNING)


if __name__ == "__main__":
    unittest.main()
