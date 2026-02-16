#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


def _xdg_dir(env_key: str, fallback: str) -> Path:
    import os

    val = os.getenv(env_key)
    if val:
        return Path(val) / "avream"
    return Path.home() / fallback / "avream"


def main() -> int:
    config_dir = _xdg_dir("XDG_CONFIG_HOME", ".config")
    profiles_path = config_dir / "profiles.json"
    sources_path = config_dir / "sources.json"

    if not profiles_path.exists() or not sources_path.exists():
        print("Nothing to migrate: profiles.json or sources.json missing")
        return 0

    profiles_data = json.loads(profiles_path.read_text(encoding="utf-8"))
    sources_data = json.loads(sources_path.read_text(encoding="utf-8"))
    profiles = profiles_data.get("profiles", []) if isinstance(profiles_data, dict) else []
    sources = sources_data.get("sources", []) if isinstance(sources_data, dict) else []

    if not isinstance(profiles, list) or not isinstance(sources, list):
        print("Invalid config format, expected list fields")
        return 1

    by_type: dict[str, list[str]] = {"rtsp": [], "file": [], "pattern": []}
    for src in sources:
        if not isinstance(src, dict):
            continue
        stype = src.get("type")
        sid = src.get("id")
        if isinstance(stype, str) and isinstance(sid, str) and stype in by_type:
            by_type[stype].append(sid)

    changed = 0
    for prof in profiles:
        if not isinstance(prof, dict):
            continue
        video = prof.get("video")
        if not isinstance(video, dict):
            continue
        backend = video.get("backend")
        if backend not in {"rtsp", "file", "pattern"}:
            continue
        if isinstance(video.get("source_id"), str) and video.get("source_id"):
            continue
        candidates = by_type.get(str(backend), [])
        if candidates:
            video["source_id"] = candidates[0]
            changed += 1

    if changed:
        profiles_path.write_text(json.dumps(profiles_data, indent=2), encoding="utf-8")
        print(f"Updated {changed} profile(s) with source_id")
    else:
        print("No profile changes required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
