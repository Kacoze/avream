"""AVream daemon package."""

from pathlib import Path

__all__ = ["__version__"]


def _read_version() -> str:
    version_file = Path(__file__).with_name("VERSION")
    try:
        value = version_file.read_text(encoding="utf-8").strip()
        if value:
            return value
    except Exception:
        pass
    return "0.0.0"


__version__ = _read_version()
