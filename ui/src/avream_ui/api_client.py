from __future__ import annotations

import asyncio
import json
import os
import threading

from aiohttp import ClientSession, ClientTimeout, UnixConnector


class ApiClient:
    def __init__(self, socket_path: str | None = None) -> None:
        self.socket_path = socket_path or os.getenv("AVREAM_SOCKET_PATH") or f"{os.getenv('XDG_RUNTIME_DIR', '/tmp')}/avream/daemon.sock"

    async def request(self, method: str, path: str, payload: dict | None = None) -> dict:
        connector = UnixConnector(path=self.socket_path)
        timeout = ClientTimeout(total=20, connect=5, sock_connect=5, sock_read=20)
        async with ClientSession(connector=connector, timeout=timeout) as session:
            async with session.request(method, f"http://localhost{path}", json=payload) as resp:
                try:
                    # Allow JSON decoding even if daemon returns wrong content-type.
                    body = await resp.json(content_type=None)
                    return {"status": resp.status, "body": body}
                except Exception:
                    text = await resp.text()
                    # Keep UI error handling consistent.
                    return {
                        "status": resp.status,
                        "body": {
                            "ok": False,
                            "data": None,
                            "error": {
                                "code": "E_BAD_RESPONSE",
                                "message": "daemon returned non-JSON response",
                                "details": {
                                    "path": path,
                                    "status": resp.status,
                                    "content_type": resp.headers.get("Content-Type"),
                                    "body": text[:1000],
                                    "hint": "restart avreamd; if problem persists, update daemon package",
                                },
                            },
                        },
                    }

    def request_sync(self, method: str, path: str, payload: dict | None = None) -> dict:
        return asyncio.run(self.request(method, path, payload))

    async def _stream_sse(self, path: str, stop_event: threading.Event, on_event) -> None:
        while not stop_event.is_set():
            try:
                connector = UnixConnector(path=self.socket_path)
                timeout = ClientTimeout(total=None, connect=5, sock_connect=5, sock_read=60)
                async with ClientSession(connector=connector, timeout=timeout) as session:
                    async with session.get(f"http://localhost{path}") as resp:
                        if resp.status != 200:
                            await asyncio.sleep(1)
                            continue
                        while not stop_event.is_set():
                            line = await resp.content.readline()
                            if not line:
                                break
                            text = line.decode("utf-8", errors="replace").strip()
                            if not text.startswith("data: "):
                                continue
                            payload = text[6:].strip()
                            try:
                                event = json.loads(payload)
                            except json.JSONDecodeError:
                                continue
                            on_event(event)
            except Exception:
                if stop_event.is_set():
                    break
                await asyncio.sleep(1)

    def stream_sse_sync(self, path: str, stop_event: threading.Event, on_event) -> None:
        asyncio.run(self._stream_sse(path, stop_event, on_event))
