from __future__ import annotations

from typing import Any

from aiohttp import ClientSession, ClientTimeout

from avreamd.api.errors import backend_error


class ReleaseClient:
    def __init__(self, *, api_base: str, repo: str) -> None:
        self._api_base = api_base
        self._repo = repo

    async def fetch_latest_release(self) -> dict[str, Any]:
        url = f"{self._api_base}/repos/{self._repo}/releases/latest"
        timeout = ClientTimeout(total=20, connect=10, sock_read=20)
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "avream-updater",
        }
        async with ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    raise backend_error("release API returned error", {"status": resp.status, "body": text[:1000]})
                payload = await resp.json(content_type=None)

        if not isinstance(payload, dict):
            raise backend_error("invalid release metadata response")

        tag_name = str(payload.get("tag_name", "")).strip()
        version = tag_name[1:] if tag_name.startswith("v") else tag_name
        if not version:
            raise backend_error("release tag is missing")

        assets = payload.get("assets")
        if not isinstance(assets, list):
            assets = []

        by_name: dict[str, dict[str, str]] = {}
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            name = asset.get("name")
            dl = asset.get("browser_download_url")
            if isinstance(name, str) and isinstance(dl, str):
                by_name[name] = {"name": name, "url": dl}

        monolith = by_name.get(f"avream_{version}_amd64.deb")
        if not monolith:
            raise backend_error("monolithic .deb asset not found", {"version": version})

        checksums = by_name.get("SHA256SUMS.txt")
        if not checksums:
            raise backend_error("SHA256SUMS.txt asset not found", {"version": version})

        release_url = payload.get("html_url")
        if not isinstance(release_url, str) or not release_url:
            release_url = f"https://github.com/{self._repo}/releases/latest"

        return {
            "version": version,
            "release_url": release_url,
            "recommended_asset": monolith,
            "assets": {
                "checksums": checksums["url"],
                "monolith": monolith["url"],
                "split_archive": by_name.get(f"avream-deb-split_{version}_amd64.tar.gz", {}).get("url", ""),
            },
        }
