from __future__ import annotations

from typing import Any

from aiohttp import web

from avreamd.api.errors import validation_error


async def read_json_object(request: web.Request) -> dict[str, Any]:
    if not request.can_read_body:
        return {}
    try:
        payload = await request.json()
    except Exception as exc:
        raise validation_error("invalid json payload") from exc
    if not isinstance(payload, dict):
        raise validation_error("payload must be a JSON object")
    return payload


def get_bool(payload: dict[str, Any], key: str, default: bool = False) -> bool:
    value = payload.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lower = value.lower()
        if lower in {"1", "true", "yes", "on"}:
            return True
        if lower in {"0", "false", "no", "off"}:
            return False
    raise validation_error(f"{key} must be a boolean")


def get_int(payload: dict[str, Any], key: str, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    value = payload.get(key, default)
    if isinstance(value, bool):
        raise validation_error(f"{key} must be an integer")
    try:
        out = int(value)
    except Exception as exc:
        raise validation_error(f"{key} must be an integer") from exc
    if minimum is not None and out < minimum:
        raise validation_error(f"{key} must be >= {minimum}")
    if maximum is not None and out > maximum:
        raise validation_error(f"{key} must be <= {maximum}")
    return out
