from __future__ import annotations

from aiohttp import web

from avreamd.api.app_keys import ADB_ADAPTER
from avreamd.api.errors import backend_error, dependency_error
from avreamd.api.schemas import success_envelope
from avreamd.api.validation import read_json_object
from avreamd.api.errors import validation_error


async def handle_android_devices(request: web.Request) -> web.Response:
    request_id = request["request_id"]
    adb = request.app[ADB_ADAPTER]
    if not adb.available:
        raise dependency_error("adb is missing", {"tool": "adb", "package": "android-tools-adb"})
    devices = await adb.list_devices()

    groups: dict[str, dict[str, object]] = {}
    available_transports: set[str] = set()

    for d in devices:
        serial = str(d.get("serial", "")).strip()
        state = str(d.get("state", "")).strip()
        if not serial:
            continue
        transport = adb.transport_of(serial)
        available_transports.add(transport)

        identity = None
        if state == "device":
            identity = await adb.device_identity(serial=serial)
        group_key = identity or f"adb:{serial}"

        g = groups.get(group_key)
        if g is None:
            g = {
                "id": group_key,
                "state": state,
                "transports": set(),
                "serials": {},
                "wifi_candidate_ip": None,
                "wifi_candidate_endpoint": None,
            }
            groups[group_key] = g

        transports = g.get("transports")
        if isinstance(transports, set):
            transports.add(transport)
        serials = g.get("serials")
        if isinstance(serials, dict):
            serials[transport] = serial

        # Prefer ready state.
        current_state = str(g.get("state", ""))
        if current_state != "device" and state == "device":
            g["state"] = "device"

        # For USB devices, probe Wi-Fi IP candidate so Scan can show endpoint
        # before adb tcpip/connect is fully set up.
        if state == "device" and transport == "usb":
            ip = await adb.detect_device_ip(serial=serial)
            if ip:
                g["wifi_candidate_ip"] = ip
                g["wifi_candidate_endpoint"] = adb.normalize_endpoint(ip)
                # Allow selecting Wi-Fi mode when candidate endpoint is known.
                available_transports.add("wifi")

    enriched: list[dict[str, object]] = []
    for g in groups.values():
        serials = g.get("serials")
        if not isinstance(serials, dict):
            serials = {}
        transports = g.get("transports")
        transports_list = sorted([str(t) for t in transports]) if isinstance(transports, set) else []
        primary_transport = "usb" if "usb" in serials else ("wifi" if "wifi" in serials else (transports_list[0] if transports_list else ""))
        primary_serial = str(serials.get(primary_transport, "")) if primary_transport else ""
        enriched.append(
            {
                "id": str(g.get("id", "")),
                "state": str(g.get("state", "")),
                "transports": transports_list,
                "serials": {str(k): str(v) for k, v in serials.items()},
                "transport": primary_transport,
                "serial": primary_serial,
                "wifi_candidate_ip": g.get("wifi_candidate_ip"),
                "wifi_candidate_endpoint": g.get("wifi_candidate_endpoint"),
            }
        )

    # Keep stable order: ready first, then USB-capable first.
    def _sort_key(x: dict[str, object]) -> tuple[int, int, str]:
        transports_obj = x.get("transports")
        transports: list[str] = []
        if isinstance(transports_obj, list):
            transports = [str(t) for t in transports_obj]
        has_usb = any(t == "usb" for t in transports)
        return (
            0 if x.get("state") == "device" else 1,
            0 if has_usb else 1,
            str(x.get("serial", "")),
        )

    enriched.sort(key=_sort_key)

    recommended = None
    recommended_id = None
    for d in enriched:
        if d.get("state") == "device":
            recommended = d.get("serial")
            recommended_id = d.get("id")
            break
    if recommended is None and enriched:
        recommended = enriched[0].get("serial")
        recommended_id = enriched[0].get("id")

    return web.json_response(
        success_envelope(
            {
                "devices": enriched,
                "recommended": recommended,
                "recommended_id": recommended_id,
                "available_transports": sorted(available_transports),
            },
            request_id=request_id,
        ),
        status=200,
    )


async def handle_android_wifi_enable(request: web.Request) -> web.Response:
    request_id = request["request_id"]
    payload = await read_json_object(request)
    serial = payload.get("serial") if isinstance(payload, dict) else None
    port = payload.get("port", 5555) if isinstance(payload, dict) else 5555

    if not isinstance(serial, str) or not serial:
        raise validation_error("serial is required")
    if not isinstance(port, int) or port < 1 or port > 65535:
        raise validation_error("port must be an integer 1..65535")

    adb = request.app[ADB_ADAPTER]
    if not adb.available:
        raise dependency_error("adb is missing", {"tool": "adb", "package": "android-tools-adb"})
    result = await adb.tcpip(serial=serial, port=port)
    if int(result.get("returncode", 1)) != 0:
        raise backend_error(
            "failed to enable adb tcpip mode",
            {"serial": serial, "port": port, "result": result},
            retryable=True,
        )
    return web.json_response(success_envelope({"serial": serial, "port": port, "result": result}, request_id=request_id), status=200)


async def handle_android_wifi_setup(request: web.Request) -> web.Response:
    request_id = request["request_id"]
    payload = await read_json_object(request)
    serial = payload.get("serial") if isinstance(payload, dict) else None
    port = payload.get("port", 5555) if isinstance(payload, dict) else 5555

    if serial is not None and (not isinstance(serial, str) or not serial):
        raise validation_error("serial must be a non-empty string when provided")
    if not isinstance(port, int) or port < 1 or port > 65535:
        raise validation_error("port must be an integer 1..65535")

    adb = request.app[ADB_ADAPTER]
    if not adb.available:
        raise dependency_error("adb is missing", {"tool": "adb", "package": "android-tools-adb"})

    result = await adb.wifi_setup(serial=serial, port=port)
    if int(result.get("returncode", 1)) != 0:
        raise backend_error(
            "failed to setup adb over Wi-Fi",
            {"serial": serial, "port": port, "result": result},
            retryable=True,
        )
    return web.json_response(
        success_envelope(
            {
                "serial": result.get("serial"),
                "ip": result.get("ip"),
                "port": result.get("port"),
                "endpoint": result.get("endpoint"),
                "result": result,
            },
            request_id=request_id,
        ),
        status=200,
    )


async def handle_android_wifi_connect(request: web.Request) -> web.Response:
    request_id = request["request_id"]
    payload = await read_json_object(request)
    endpoint = payload.get("endpoint") if isinstance(payload, dict) else None
    if not isinstance(endpoint, str) or not endpoint:
        raise validation_error("endpoint is required")

    adb = request.app[ADB_ADAPTER]
    if not adb.available:
        raise dependency_error("adb is missing", {"tool": "adb", "package": "android-tools-adb"})
    result = await adb.connect(endpoint=endpoint)
    if int(result.get("returncode", 1)) != 0:
        raise backend_error(
            "failed to connect adb endpoint",
            {"endpoint": endpoint, "result": result},
            retryable=True,
        )
    return web.json_response(success_envelope({"endpoint": adb.normalize_endpoint(endpoint), "result": result}, request_id=request_id), status=200)


async def handle_android_wifi_disconnect(request: web.Request) -> web.Response:
    request_id = request["request_id"]
    payload = await read_json_object(request)
    endpoint = payload.get("endpoint") if isinstance(payload, dict) else None
    if not isinstance(endpoint, str) or not endpoint:
        raise validation_error("endpoint is required")

    adb = request.app[ADB_ADAPTER]
    if not adb.available:
        raise dependency_error("adb is missing", {"tool": "adb", "package": "android-tools-adb"})
    result = await adb.disconnect(endpoint=endpoint)
    if int(result.get("returncode", 1)) != 0:
        raise backend_error(
            "failed to disconnect adb endpoint",
            {"endpoint": endpoint, "result": result},
            retryable=True,
        )
    return web.json_response(success_envelope({"endpoint": adb.normalize_endpoint(endpoint), "result": result}, request_id=request_id), status=200)


def register_android_routes(app: web.Application) -> None:
    app.router.add_get("/android/devices", handle_android_devices)
    app.router.add_post("/android/wifi/enable", handle_android_wifi_enable)
    app.router.add_post("/android/wifi/setup", handle_android_wifi_setup)
    app.router.add_post("/android/wifi/connect", handle_android_wifi_connect)
    app.router.add_post("/android/wifi/disconnect", handle_android_wifi_disconnect)
