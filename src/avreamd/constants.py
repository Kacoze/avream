from pathlib import Path


APP_NAME = "avream"
DAEMON_NAME = "avreamd"
API_VERSION = "v1"
SOCKET_FILENAME = "daemon.sock"
DEFAULT_LOG_LEVEL = "INFO"

# Network defaults
ADB_DEFAULT_PORT: int = 5555

# Reconnect defaults
DEFAULT_RECONNECT_BACKOFF_MS: int = 1500
DEFAULT_RECONNECT_MAX_ATTEMPTS: int = 3

# Logging / storage limits
UPDATE_LOG_MAXLEN: int = 300
INSTALL_STDOUT_TAIL: int = 1000    # tail kept in success result
INSTALL_STDERR_TAIL: int = 3000    # tail kept in failure detail
HTTP_BODY_TRUNCATE: int = 1000     # error body logged from HTTP responses
DOWNLOAD_CHUNK_SIZE: int = 1024 * 64


def fallback_runtime_dir(uid: int) -> Path:
    return Path(f"/tmp/{APP_NAME}-{uid}")
