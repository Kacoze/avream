from __future__ import annotations

import gettext
from pathlib import Path

_DOMAIN = "avream"
_LOCALE_DIR = Path(__file__).parent / "locale"
_translator: gettext.NullTranslations = gettext.NullTranslations()

# Language code → display name in native language
LANGUAGES: dict[str, str] = {
    "en": "English",
    "pl": "Polski",
    "es": "Español",
    "ar": "العربية",
    "zh_CN": "中文",
}


def setup(lang: str | None) -> None:
    global _translator
    if lang and lang != "en":
        _translator = gettext.translation(
            _DOMAIN, localedir=str(_LOCALE_DIR), languages=[lang], fallback=True
        )
    else:
        _translator = gettext.NullTranslations()


def _(msg: str) -> str:  # noqa: N802
    return _translator.gettext(msg)
