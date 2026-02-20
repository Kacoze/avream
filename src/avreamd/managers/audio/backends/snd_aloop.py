from __future__ import annotations

from avreamd.managers.privilege_client import PrivilegeClient


class SndAloopAudioBackend:
    def __init__(self, *, privilege_client: PrivilegeClient) -> None:
        self._privilege_client = privilege_client

    async def start(self) -> None:
        await self._privilege_client.call("snd_aloop.load", {})

    async def stop(self) -> None:
        try:
            await self._privilege_client.call("snd_aloop.unload", {})
        except Exception:
            pass
