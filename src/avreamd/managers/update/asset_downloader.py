from __future__ import annotations

from pathlib import Path

from aiohttp import ClientSession, ClientTimeout

from avreamd.api.errors import backend_error


class AssetDownloader:
    async def download_file(self, url: str, path: Path) -> None:
        timeout = ClientTimeout(total=120, connect=20, sock_read=120)
        headers = {"Accept": "application/octet-stream", "User-Agent": "avream-updater"}
        async with ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    raise backend_error("download failed", {"url": url, "status": resp.status, "body": text[:1000]})
                with path.open("wb") as handle:
                    async for chunk in resp.content.iter_chunked(1024 * 64):
                        handle.write(chunk)
