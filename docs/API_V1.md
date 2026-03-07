# AVream API v1 (Phone-first)

Developer contract for AVream daemon API used by GUI and CLI.

## Transport

HTTP+JSON over UNIX socket:

```
$XDG_RUNTIME_DIR/avream/daemon.sock
```

Fallback when `$XDG_RUNTIME_DIR` is unset: `/tmp/avream-<uid>/daemon.sock`

## Envelope

**Success:**
```json
{
  "ok": true,
  "data": { ... },
  "error": null,
  "request_id": "<uuid>",
  "ts": "<ISO 8601 UTC>"
}
```

**Error:**
```json
{
  "ok": false,
  "data": null,
  "error": {
    "code": "E_CONFLICT",
    "message": "human-readable description",
    "details": { ... },
    "retryable": false
  },
  "request_id": "<uuid>",
  "ts": "<ISO 8601 UTC>"
}
```

## Endpoints

### `GET /status`

Returns daemon and subsystem runtime state.

**Response `data`:**
```json
{
  "service": {
    "app": "avream",
    "daemon": "avreamd",
    "api_version": "v1",
    "socket_path": "/run/user/1000/avream/daemon.sock",
    "helper": { ... }
  },
  "video_runtime": {
    "active_source": null,
    "active_process": null,
    "last_exit_code": null,
    "reconnect": {
      "enabled": true,
      "state": "idle",
      "attempt": 0,
      "max_attempts": 3,
      "backoff_ms": 1500,
      "next_retry_in_ms": null,
      "last_exit_code": null
    },
    "log_pointers": {
      "video_android": "/path/to/latest.log"
    }
  },
  "update_runtime": {
    "current_version": "1.2.3",
    "latest_version": "1.2.3",
    "update_available": false,
    "channel": "stable",
    "last_checked_at": null,
    "last_error": null,
    "install_state": "IDLE",
    "latest_release_url": "https://github.com/Kacoze/avream/releases/latest",
    "recommended_asset": null,
    "assets": {},
    "progress": 0
  },
  "runtime": { ... }
}
```

---

### `POST /video/start`

Starts video streaming from an Android device.

**Body (all fields optional):**
```json
{
  "serial": "emulator-5554",
  "camera_facing": "front",
  "camera_rotation": 0,
  "preview_window": false
}
```

| Field | Type | Values | Default |
|---|---|---|---|
| `serial` | string | ADB serial | auto-select |
| `camera_facing` | string | `"front"`, `"back"` | `"front"` |
| `camera_rotation` | integer | `0`, `90`, `180`, `270` | `0` |
| `preview_window` | boolean | | `false` |

---

### `POST /video/stop`

Stops active video stream. Triggers best-effort v4l2loopback reload after stop.

No request body required.

---

### `POST /video/reset`

Resets the v4l2loopback device. Stops any running stream first.

**Body (all fields optional):**
```json
{ "force": false }
```

| Field | Type | Default | Notes |
|---|---|---|---|
| `force` | boolean | `false` | Force reset even when device is in use |

---

### `POST /audio/start`

Starts audio routing from the Android device.

**Body (all fields optional):**
```json
{ "backend": "pipewire" }
```

| Field | Type | Values | Default |
|---|---|---|---|
| `backend` | string | `"pipewire"`, `"snd_aloop"` | `"pipewire"` |

---

### `POST /audio/stop`

Stops active audio routing.

No request body required.

---

### `GET /android/devices`

Lists connected Android devices, grouped by physical device identity.

**Response `data`:**
```json
{
  "devices": [
    {
      "id": "Pixel_7_ABC123",
      "state": "device",
      "transports": ["usb", "wifi"],
      "serials": {
        "usb": "ABC123",
        "wifi": "192.168.1.50:5555"
      },
      "transport": "usb",
      "serial": "ABC123",
      "wifi_candidate_ip": "192.168.1.50",
      "wifi_candidate_endpoint": "192.168.1.50:5555"
    }
  ],
  "recommended": "ABC123",
  "recommended_id": "Pixel_7_ABC123",
  "available_transports": ["usb", "wifi"]
}
```

- `state`: `"device"` (ready), `"unauthorized"`, `"offline"`, etc.
- `transport` / `serial`: primary recommended transport and its serial.
- `wifi_candidate_ip/endpoint`: detected from USB-connected device; available even before `wifi/setup` completes.
- Devices are sorted: ready first, USB-capable first.

---

### `POST /android/wifi/enable`

Enables `adb tcpip` mode on a USB-connected device (step 1 of manual Wi-Fi setup).

**Body:**
```json
{ "serial": "ABC123", "port": 5555 }
```

| Field | Type | Required | Default |
|---|---|---|---|
| `serial` | string | yes | |
| `port` | integer 1–65535 | no | `5555` |

---

### `POST /android/wifi/setup`

Recommended Wi-Fi setup flow: enables `adb tcpip`, detects device IP over USB, and connects automatically.

**Body (all fields optional):**
```json
{ "serial": "ABC123", "port": 5555 }
```

**Response `data`:**
```json
{
  "serial": "ABC123",
  "ip": "192.168.1.50",
  "port": 5555,
  "endpoint": "192.168.1.50:5555",
  "result": { ... }
}
```

---

### `POST /android/wifi/connect`

Connects to an already-enabled Wi-Fi ADB endpoint. Waits up to 6 s for device to become ready.

**Body:**
```json
{ "endpoint": "192.168.1.50:5555" }
```

`endpoint` accepts `IP` or `IP:PORT` (port defaults to `5555`).

---

### `POST /android/wifi/disconnect`

Disconnects a Wi-Fi ADB endpoint.

**Body:**
```json
{ "endpoint": "192.168.1.50:5555" }
```

---

### `GET /update/status`

Returns current update runtime state (same shape as `update_runtime` in `/status`).

---

### `POST /update/check`

Checks GitHub for a newer release.

**Body (all fields optional):**
```json
{ "force": false }
```

---

### `POST /update/install`

Downloads and installs the latest release package (Debian `.deb` with checksum verification).

**Body (all fields optional):**
```json
{ "target": "latest", "allow_stop_streams": false }
```

| Field | Type | Default | Notes |
|---|---|---|---|
| `target` | string | `"latest"` | |
| `allow_stop_streams` | boolean | `false` | Stop active streams if required |

---

### `GET /update/logs`

Returns in-memory update log entries (capped at 300 entries).

---

### `GET /update/config`

Returns current update configuration.

**Response `data`:**
```json
{ "auto_check": "daily", "channel": "stable" }
```

---

### `POST /update/config`

Updates update configuration. All fields optional.

**Body:**
```json
{ "auto_check": "daily", "channel": "stable" }
```

| Field | Values |
|---|---|
| `auto_check` | `"off"`, `"daily"`, `"weekly"` |
| `channel` | `"stable"` |

---

## Error Codes

| Code | HTTP | Retryable | Description |
|---|---|---|---|
| `E_VALIDATION` | 400 | no | Invalid request body or field value |
| `E_CONFLICT` | 409 | no | Action conflicts with current runtime state |
| `E_BUSY_DEVICE` | 409 | yes | Reset/reload blocked by in-use `/dev/video*` |
| `E_PERMISSION` | 403 | no | pkexec/polkit/helper invocation failure |
| `E_DEP_MISSING` | 412 | no | Missing runtime dependency (e.g. `adb`) |
| `E_BACKEND_FAILED` | 502 | yes | Backend process failed or exited unexpectedly |
| `E_TIMEOUT` | 504 | yes | Helper invocation timeout |
| `E_UNSUPPORTED` | 400 | no | Operation not supported in current configuration |
| `E_NOT_IMPLEMENTED` | 501 | no | Endpoint defined but not yet implemented |

---

## Removed from public API (phone-first mode)

- `/sources/*`
- `/profiles/*`
- `/doctor/*`
- `/fix/*`
- `/logs/*`
- `/video/reconnect/stop`

---

## Minimal status probe

```bash
curl --unix-socket "$XDG_RUNTIME_DIR/avream/daemon.sock" http://localhost/status
```
