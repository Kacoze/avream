# AVream API v1 (Phone-first)

Developer contract for AVream daemon API used by GUI and CLI.

Transport:
- HTTP+JSON over UNIX socket (`$XDG_RUNTIME_DIR/avream/daemon.sock`)

Envelope:
- Success: `{ ok: true, data: {...}, error: null, request_id, ts }`
- Error: `{ ok: false, data: null, error: { code, message, details, retryable }, request_id, ts }`

Implemented endpoints:
- `GET /status`
- `POST /video/start` body: `{ serial?: string, camera_facing?: "front" | "back", preview_window?: boolean }`
- `POST /video/stop`
- `POST /video/reset` body: `{ force?: boolean }`
- `POST /audio/start` body: `{ backend?: "pipewire" | "snd_aloop" }`
- `POST /audio/stop`
- `GET /update/status`
- `POST /update/check` body: `{ force?: boolean }`
- `POST /update/install` body: `{ target?: "latest", allow_stop_streams?: boolean }`
- `GET /update/logs`
- `GET /update/config`
- `POST /update/config` body: `{ auto_check?: "off" | "daily" | "weekly", channel?: "stable" }`
- `GET /android/devices`
- `POST /android/wifi/enable` body: `{ serial: string, port?: number }`
- `POST /android/wifi/setup` body: `{ serial?: string, port?: number }`
- `POST /android/wifi/connect` body: `{ endpoint: string }`
- `POST /android/wifi/disconnect` body: `{ endpoint: string }`

Notes:
- `wifi/setup` is the recommended flow: it enables `adb tcpip`, detects phone IP over USB, and connects automatically.
- `endpoint` accepts `IP` or `IP:PORT` (`5555` is used when port is omitted).
- Updates currently install monolithic Debian package (`avream_<version>_amd64.deb`) with checksum verification.

Removed from public API in phone-first mode:
- `/sources/*`
- `/profiles/*`
- `/doctor/*`
- `/fix/*`
- `/logs/*`
- `/video/reconnect/stop`

Error mapping notes:
- `E_BUSY_DEVICE`: reset/reload blocked by in-use `/dev/video*`
- `E_PERMISSION`: pkexec/polkit/helper invocation failure
- `E_TIMEOUT`: helper invocation timeout
- `E_CONFLICT`: action conflicts with current runtime state
- `E_BACKEND_FAILED`: backend process failed or exited unexpectedly
- `E_DEP_MISSING`: missing runtime dependency

Minimal status probe:

```bash
curl --unix-socket "$XDG_RUNTIME_DIR/avream/daemon.sock" http://localhost/status
```
