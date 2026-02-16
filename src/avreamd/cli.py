from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any

from aiohttp import ClientSession, ClientTimeout, UnixConnector

from avreamd.config import resolve_paths


class CliApiClient:
    def __init__(self, socket_path: str, timeout_s: float = 20.0) -> None:
        self.socket_path = socket_path
        self.timeout_s = timeout_s

    async def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        connector = UnixConnector(path=self.socket_path)
        timeout = ClientTimeout(total=self.timeout_s, connect=5, sock_connect=5, sock_read=self.timeout_s)
        try:
            async with ClientSession(connector=connector, timeout=timeout) as session:
                async with session.request(method, f"http://localhost{path}", json=payload) as resp:
                    try:
                        body = await resp.json(content_type=None)
                    except Exception:
                        body = {
                            "ok": False,
                            "data": None,
                            "error": {
                                "code": "E_BAD_RESPONSE",
                                "message": "daemon returned non-JSON response",
                            },
                        }
                    return {"status": int(resp.status), "body": body}
        except Exception as exc:
            return {
                "status": 0,
                "body": {
                    "ok": False,
                    "data": None,
                    "error": {
                        "code": "E_DAEMON_UNREACHABLE",
                        "message": str(exc),
                        "details": {"socket_path": self.socket_path},
                    },
                },
            }

    def request_sync(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return asyncio.run(self.request(method, path, payload))


def _print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def _request_data(
    api: CliApiClient,
    *,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    result = api.request_sync(method, path, payload)
    body = result.get("body") if isinstance(result, dict) else {}
    status = result.get("status") if isinstance(result, dict) else 0
    if not isinstance(body, dict) or not body.get("ok"):
        err = body.get("error", {}) if isinstance(body, dict) else {}
        code = str(err.get("code", "E_UNKNOWN"))
        message = str(err.get("message", "request failed"))
        details = err.get("details")
        print(f"Error ({status}): {code}: {message}", file=sys.stderr)
        if isinstance(details, dict) and details:
            _print_json({"details": details})
        return None, result
    data = body.get("data")
    if not isinstance(data, dict):
        return {}, result
    return data, result


def _pick_serial_for_mode(devices_data: dict[str, Any], mode: str) -> str | None:
    devices = devices_data.get("devices") if isinstance(devices_data, dict) else None
    if not isinstance(devices, list) or not devices:
        return None

    preferred_transport = "wifi" if mode == "wifi" else "usb"
    fallback_transport = "usb" if mode == "wifi" else "wifi"

    for dev in devices:
        if not isinstance(dev, dict) or dev.get("state") != "device":
            continue
        serials = dev.get("serials")
        if isinstance(serials, dict):
            cand = serials.get(preferred_transport)
            if isinstance(cand, str) and cand:
                return cand

    for dev in devices:
        if not isinstance(dev, dict) or dev.get("state") != "device":
            continue
        serials = dev.get("serials")
        if isinstance(serials, dict):
            cand = serials.get(fallback_transport)
            if isinstance(cand, str) and cand:
                return cand

    recommended = devices_data.get("recommended") if isinstance(devices_data, dict) else None
    if isinstance(recommended, str) and recommended:
        return recommended
    return None


def cmd_status(args: argparse.Namespace, api: CliApiClient) -> int:
    data, result = _request_data(api, method="GET", path="/status")
    if data is None:
        return 1
    if args.json:
        _print_json(result)
        return 0

    runtime = data.get("runtime", {}) if isinstance(data, dict) else {}
    video = runtime.get("video", {}) if isinstance(runtime, dict) else {}
    audio = runtime.get("audio", {}) if isinstance(runtime, dict) else {}
    video_rt = data.get("video_runtime", {}) if isinstance(data, dict) else {}
    update_rt = data.get("update_runtime", {}) if isinstance(data, dict) else {}
    service = data.get("service", {}) if isinstance(data, dict) else {}
    helper = service.get("helper", {}) if isinstance(service, dict) else {}
    active_source = video_rt.get("active_source", {}) if isinstance(video_rt, dict) else {}

    print(f"Camera: {video.get('state', 'unknown')}")
    print(f"Microphone: {audio.get('state', 'unknown')}")
    if isinstance(update_rt, dict):
        latest = update_rt.get("latest_version")
        available = bool(update_rt.get("update_available", False))
        if latest:
            print(f"Update: {'available' if available else 'up-to-date'} (latest: {latest})")
    if isinstance(active_source, dict) and active_source:
        serial = active_source.get("serial")
        facing = active_source.get("camera_facing")
        preview = active_source.get("preview_window")
        print(f"Active phone: {serial} | lens: {facing} | preview: {preview}")
    runner = helper.get("effective_runner") if isinstance(helper, dict) else None
    if runner:
        print(f"Helper runner: {runner}")
    return 0


def cmd_devices(args: argparse.Namespace, api: CliApiClient) -> int:
    data, result = _request_data(api, method="GET", path="/android/devices")
    if data is None:
        return 1
    if args.json:
        _print_json(result)
        return 0

    devices = data.get("devices") if isinstance(data, dict) else None
    recommended_id = data.get("recommended_id") if isinstance(data, dict) else None
    if not isinstance(devices, list) or not devices:
        print("No phones found.")
        return 0

    for dev in devices:
        if not isinstance(dev, dict):
            continue
        marker = "*" if recommended_id and dev.get("id") == recommended_id else " "
        state = str(dev.get("state", "unknown"))
        dev_id = str(dev.get("id", ""))
        serials = dev.get("serials") if isinstance(dev.get("serials"), dict) else {}
        transports = dev.get("transports") if isinstance(dev.get("transports"), list) else []
        transport_text = ",".join(str(t) for t in transports)
        usb = serials.get("usb") if isinstance(serials, dict) else None
        wifi = serials.get("wifi") if isinstance(serials, dict) else None
        candidate = dev.get("wifi_candidate_endpoint")
        print(f"{marker} [{state}] id={dev_id} transports={transport_text}")
        if usb:
            print(f"    usb:  {usb}")
        if wifi:
            print(f"    wifi: {wifi}")
        if candidate:
            print(f"    wifi-candidate: {candidate}")
    print("\n* recommended")
    return 0


def cmd_wifi_setup(args: argparse.Namespace, api: CliApiClient) -> int:
    payload: dict[str, Any] = {"port": int(args.port)}
    if args.serial:
        payload["serial"] = args.serial
    data, result = _request_data(api, method="POST", path="/android/wifi/setup", payload=payload)
    if data is None:
        return 1
    if args.json:
        _print_json(result)
        return 0
    serial = data.get("serial")
    endpoint = data.get("endpoint")
    print(f"Wi-Fi ready: {serial} -> {endpoint}")
    return 0


def cmd_wifi_connect(args: argparse.Namespace, api: CliApiClient) -> int:
    data, result = _request_data(
        api,
        method="POST",
        path="/android/wifi/connect",
        payload={"endpoint": args.endpoint},
    )
    if data is None:
        return 1
    if args.json:
        _print_json(result)
        return 0
    print(f"Connected: {data.get('endpoint', args.endpoint)}")
    return 0


def cmd_wifi_disconnect(args: argparse.Namespace, api: CliApiClient) -> int:
    data, result = _request_data(
        api,
        method="POST",
        path="/android/wifi/disconnect",
        payload={"endpoint": args.endpoint},
    )
    if data is None:
        return 1
    if args.json:
        _print_json(result)
        return 0
    print(f"Disconnected: {data.get('endpoint', args.endpoint)}")
    return 0


def cmd_camera_start(args: argparse.Namespace, api: CliApiClient) -> int:
    payload: dict[str, Any] = {
        "camera_facing": args.lens,
        "preview_window": bool(args.preview_window),
    }
    if args.serial:
        payload["serial"] = args.serial
    data, result = _request_data(api, method="POST", path="/video/start", payload=payload)
    if data is None:
        return 1
    if args.json:
        _print_json(result)
        return 0
    source = data.get("source", {}) if isinstance(data, dict) else {}
    serial = source.get("serial") if isinstance(source, dict) else None
    print(f"Camera started{f' on {serial}' if serial else ''}.")
    return 0


def cmd_camera_stop(args: argparse.Namespace, api: CliApiClient) -> int:
    data, result = _request_data(api, method="POST", path="/video/stop", payload={})
    if data is None:
        return 1
    if args.json:
        _print_json(result)
        return 0
    print("Camera stopped.")
    return 0


def cmd_camera_reset(args: argparse.Namespace, api: CliApiClient) -> int:
    data, result = _request_data(api, method="POST", path="/video/reset", payload={"force": bool(args.force)})
    if data is None:
        return 1
    if args.json:
        _print_json(result)
        return 0
    print("Camera reset completed.")
    return 0


def cmd_mic_start(args: argparse.Namespace, api: CliApiClient) -> int:
    data, result = _request_data(api, method="POST", path="/audio/start", payload={"backend": args.backend})
    if data is None:
        return 1
    if args.json:
        _print_json(result)
        return 0
    print(f"Microphone started ({data.get('backend', args.backend)}).")
    return 0


def cmd_mic_stop(args: argparse.Namespace, api: CliApiClient) -> int:
    data, result = _request_data(api, method="POST", path="/audio/stop", payload={})
    if data is None:
        return 1
    if args.json:
        _print_json(result)
        return 0
    print("Microphone stopped.")
    return 0


def cmd_start(args: argparse.Namespace, api: CliApiClient) -> int:
    serial = args.serial

    if args.mode == "wifi":
        wifi_payload: dict[str, Any] = {"port": int(args.port)}
        if serial:
            wifi_payload["serial"] = serial
        wifi_data, _ = _request_data(api, method="POST", path="/android/wifi/setup", payload=wifi_payload)
        if wifi_data is None:
            return 1
        endpoint = wifi_data.get("endpoint") if isinstance(wifi_data, dict) else None
        if not isinstance(endpoint, str) or not endpoint:
            print("Error: Wi-Fi setup returned no endpoint.", file=sys.stderr)
            return 1
        serial = endpoint
    elif not serial:
        devices_data, _ = _request_data(api, method="GET", path="/android/devices")
        if devices_data is None:
            return 1
        serial = _pick_serial_for_mode(devices_data, "usb")
        if not serial:
            print("Error: no ready phone found. Use `avream devices` first.", file=sys.stderr)
            return 1

    payload: dict[str, Any] = {
        "camera_facing": args.lens,
        "preview_window": bool(args.preview_window),
    }
    if serial:
        payload["serial"] = serial

    data, result = _request_data(api, method="POST", path="/video/start", payload=payload)
    if data is None:
        return 1
    if args.json:
        _print_json(result)
        return 0
    print(f"Camera started on {serial}.")
    return 0


def cmd_update_status(args: argparse.Namespace, api: CliApiClient) -> int:
    data, result = _request_data(api, method="GET", path="/update/status")
    if data is None:
        return 1
    if args.json:
        _print_json(result)
        return 0

    current = data.get("current_version")
    latest = data.get("latest_version")
    available = bool(data.get("update_available", False))
    install_state = data.get("install_state")
    print(f"Current: {current}")
    print(f"Latest: {latest}")
    print(f"Update available: {'yes' if available else 'no'}")
    print(f"Install state: {install_state}")
    if available:
        url = data.get("latest_release_url")
        if isinstance(url, str) and url:
            print(f"Release: {url}")
    last_error = data.get("last_error")
    if isinstance(last_error, dict) and last_error:
        print(f"Last error: {last_error.get('message', 'unknown error')}")
    return 0


def cmd_update_check(args: argparse.Namespace, api: CliApiClient) -> int:
    data, result = _request_data(api, method="POST", path="/update/check", payload={"force": bool(args.force)})
    if data is None:
        return 1
    if args.json:
        _print_json(result)
        return 0
    current = data.get("current_version")
    latest = data.get("latest_version")
    available = bool(data.get("update_available", False))
    print(f"Current: {current}")
    print(f"Latest: {latest}")
    print("Update available." if available else "Already up to date.")
    return 0


def cmd_update_install(args: argparse.Namespace, api: CliApiClient) -> int:
    payload = {
        "target": "latest",
        "allow_stop_streams": bool(args.allow_stop_streams),
    }
    data, result = _request_data(api, method="POST", path="/update/install", payload=payload)
    if data is None:
        return 1
    if args.json:
        _print_json(result)
        return 0
    if bool(data.get("already_up_to_date", False)):
        print("Already up to date.")
        return 0
    print(f"Update installed: {data.get('target_version')}")
    if data.get("restart_scheduled"):
        print("Daemon restart scheduled.")
    return 0


def cmd_update_logs(args: argparse.Namespace, api: CliApiClient) -> int:
    data, result = _request_data(api, method="GET", path="/update/logs")
    if data is None:
        return 1
    if args.json:
        _print_json(result)
        return 0
    events = data.get("events") if isinstance(data, dict) else None
    if not isinstance(events, list) or not events:
        print("No update events.")
        return 0
    for evt in events[-30:]:
        if not isinstance(evt, dict):
            continue
        ts = evt.get("ts", "")
        name = evt.get("event", "")
        print(f"[{ts}] {name}")
    return 0


def cmd_update_config_get(args: argparse.Namespace, api: CliApiClient) -> int:
    data, result = _request_data(api, method="GET", path="/update/config")
    if data is None:
        return 1
    if args.json:
        _print_json(result)
        return 0
    print(f"auto_check: {data.get('auto_check')}")
    print(f"channel: {data.get('channel')}")
    return 0


def cmd_update_config_set(args: argparse.Namespace, api: CliApiClient) -> int:
    payload: dict[str, Any] = {}
    if args.auto_check is not None:
        payload["auto_check"] = args.auto_check
    if args.channel is not None:
        payload["channel"] = args.channel
    if not payload:
        print("Nothing to update. Use --auto-check and/or --channel.", file=sys.stderr)
        return 2
    data, result = _request_data(api, method="POST", path="/update/config", payload=payload)
    if data is None:
        return 1
    if args.json:
        _print_json(result)
        return 0
    print("Update config saved.")
    print(f"auto_check: {data.get('auto_check')}")
    print(f"channel: {data.get('channel')}")
    return 0


def _default_socket_path() -> str:
    env = os.getenv("AVREAM_SOCKET_PATH")
    if env:
        return env
    return str(resolve_paths().socket_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="avream", description="AVream CLI for phone camera/mic workflows")
    parser.add_argument("--socket-path", default=_default_socket_path(), help="UNIX socket path for avreamd")
    parser.add_argument("--timeout", type=float, default=20.0, help="Request timeout in seconds")
    parser.add_argument("--json", action="store_true", help="Print full API response JSON")

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Show daemon and runtime status")
    sub.add_parser("devices", help="List detected Android devices")

    wifi = sub.add_parser("wifi", help="Manage ADB over Wi-Fi")
    wifi_sub = wifi.add_subparsers(dest="wifi_cmd", required=True)
    wifi_setup = wifi_sub.add_parser("setup", help="Enable tcpip and connect one phone")
    wifi_setup.add_argument("--serial", help="USB serial to configure")
    wifi_setup.add_argument("--port", type=int, default=5555, help="ADB tcpip port")
    wifi_connect = wifi_sub.add_parser("connect", help="Connect to endpoint")
    wifi_connect.add_argument("endpoint", help="IP or IP:PORT")
    wifi_disconnect = wifi_sub.add_parser("disconnect", help="Disconnect endpoint")
    wifi_disconnect.add_argument("endpoint", help="IP or IP:PORT")

    camera = sub.add_parser("camera", help="Control camera streaming")
    camera_sub = camera.add_subparsers(dest="camera_cmd", required=True)
    camera_start = camera_sub.add_parser("start", help="Start camera")
    camera_start.add_argument("--serial", help="ADB serial/endpoint to use")
    camera_start.add_argument("--lens", choices=["front", "back"], default="front")
    camera_start.add_argument("--preview-window", action="store_true", help="Show scrcpy preview window")
    camera_sub.add_parser("stop", help="Stop camera")
    camera_reset = camera_sub.add_parser("reset", help="Reset virtual camera")
    camera_reset.add_argument("--force", action="store_true", help="Force reset when possible")

    mic = sub.add_parser("mic", help="Control AVream microphone")
    mic_sub = mic.add_subparsers(dest="mic_cmd", required=True)
    mic_start = mic_sub.add_parser("start", help="Start microphone bridge")
    mic_start.add_argument("--backend", choices=["pipewire", "snd_aloop"], default="pipewire")
    mic_sub.add_parser("stop", help="Stop microphone bridge")

    start = sub.add_parser("start", help="One-shot: prepare phone and start camera")
    start.add_argument("--mode", choices=["usb", "wifi"], default="wifi")
    start.add_argument("--serial", help="Preferred serial. For Wi-Fi, USB serial is accepted too")
    start.add_argument("--port", type=int, default=5555, help="Wi-Fi setup port when --mode=wifi")
    start.add_argument("--lens", choices=["front", "back"], default="front")
    start.add_argument("--preview-window", action="store_true", help="Show scrcpy preview window")

    update = sub.add_parser("update", help="Check and install AVream updates")
    update_sub = update.add_subparsers(dest="update_cmd", required=True)
    update_status = update_sub.add_parser("status", help="Show update status")
    update_status.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    update_check = update_sub.add_parser("check", help="Check latest release")
    update_check.add_argument("--force", action="store_true", help="Force refresh from release API")
    update_check.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    update_install = update_sub.add_parser("install", help="Install latest monolithic .deb")
    update_install.add_argument(
        "--allow-stop-streams",
        action="store_true",
        help="Allow stopping camera/microphone if running",
    )
    update_install.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    update_logs = update_sub.add_parser("logs", help="Show update operation logs")
    update_logs.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    update_cfg = update_sub.add_parser("config", help="Get or set update config")
    update_cfg_sub = update_cfg.add_subparsers(dest="update_cfg_cmd", required=True)
    update_cfg_get = update_cfg_sub.add_parser("get", help="Show current update config")
    update_cfg_get.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    update_cfg_set = update_cfg_sub.add_parser("set", help="Set update config")
    update_cfg_set.add_argument("--auto-check", choices=["off", "daily", "weekly"])
    update_cfg_set.add_argument("--channel", choices=["stable"])
    update_cfg_set.add_argument("--json", action="store_true", help=argparse.SUPPRESS)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv or sys.argv[1:])
    api = CliApiClient(socket_path=args.socket_path, timeout_s=float(args.timeout))

    if args.command == "status":
        return cmd_status(args, api)
    if args.command == "devices":
        return cmd_devices(args, api)

    if args.command == "wifi":
        if args.wifi_cmd == "setup":
            return cmd_wifi_setup(args, api)
        if args.wifi_cmd == "connect":
            return cmd_wifi_connect(args, api)
        if args.wifi_cmd == "disconnect":
            return cmd_wifi_disconnect(args, api)
        parser.error("unknown wifi subcommand")

    if args.command == "camera":
        if args.camera_cmd == "start":
            return cmd_camera_start(args, api)
        if args.camera_cmd == "stop":
            return cmd_camera_stop(args, api)
        if args.camera_cmd == "reset":
            return cmd_camera_reset(args, api)
        parser.error("unknown camera subcommand")

    if args.command == "mic":
        if args.mic_cmd == "start":
            return cmd_mic_start(args, api)
        if args.mic_cmd == "stop":
            return cmd_mic_stop(args, api)
        parser.error("unknown mic subcommand")

    if args.command == "start":
        return cmd_start(args, api)

    if args.command == "update":
        if args.update_cmd == "status":
            return cmd_update_status(args, api)
        if args.update_cmd == "check":
            return cmd_update_check(args, api)
        if args.update_cmd == "install":
            return cmd_update_install(args, api)
        if args.update_cmd == "logs":
            return cmd_update_logs(args, api)
        if args.update_cmd == "config":
            if args.update_cfg_cmd == "get":
                return cmd_update_config_get(args, api)
            if args.update_cfg_cmd == "set":
                return cmd_update_config_set(args, api)
            parser.error("unknown update config subcommand")
        parser.error("unknown update subcommand")

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
