from __future__ import annotations

import argparse
import asyncio
import logging
from logging.handlers import RotatingFileHandler
import os
import signal
import sys

from avreamd.app import AvreamDaemon
from avreamd.config import ensure_directories, resolve_paths
from avreamd.constants import DEFAULT_LOG_LEVEL


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AVream daemon")
    parser.add_argument(
        "--socket-path",
        default=os.getenv("AVREAM_SOCKET_PATH"),
        help="Override unix socket path",
    )
    parser.add_argument(
        "--log-level",
        default=os.getenv("AVREAM_LOG_LEVEL", DEFAULT_LOG_LEVEL),
        help="Python log level",
    )
    return parser.parse_args(argv)


def configure_logging(paths, log_level: str) -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    root.addHandler(stream)

    file_handler = RotatingFileHandler(paths.log_dir / "avreamd.log", maxBytes=1_000_000, backupCount=3)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)


async def _run(args: argparse.Namespace) -> int:
    paths = resolve_paths(socket_override=args.socket_path)
    ensure_directories(paths)
    configure_logging(paths, args.log_level)
    daemon = AvreamDaemon(paths)

    loop = asyncio.get_running_loop()

    def _on_signal() -> None:
        daemon.request_shutdown()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _on_signal)
        except NotImplementedError:
            signal.signal(sig, lambda *_: _on_signal())

    await daemon.start()
    await daemon.wait_until_shutdown()
    await daemon.stop()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        return asyncio.run(_run(args))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
