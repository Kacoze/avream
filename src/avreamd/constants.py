from pathlib import Path


APP_NAME = "avream"
DAEMON_NAME = "avreamd"
API_VERSION = "v1"
SOCKET_FILENAME = "daemon.sock"
DEFAULT_LOG_LEVEL = "INFO"


def fallback_runtime_dir(uid: int) -> Path:
    return Path(f"/tmp/{APP_NAME}-{uid}")
