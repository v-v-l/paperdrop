"""Internationalization module for the application.

Loads JSON locale files and provides a get_text() helper with
string interpolation. Falls back to English when a locale is
not available.
"""

import json
from functools import lru_cache
from pathlib import Path

from logs_flow import ErrorCodes, create_logger

logger = create_logger(service="i18n")

LOCALES_DIR = Path(__file__).parent / "locales"
DEFAULT_LOCALE = "en"

# In-memory cache: {(locale, module): {key: value}}
_cache: dict[tuple[str, str], dict[str, str]] = {}


def _load_module(locale: str, module: str) -> dict[str, str]:
    """Load a single locale module JSON file into the cache."""
    cache_key = (locale, module)
    if cache_key in _cache:
        return _cache[cache_key]

    file_path = LOCALES_DIR / locale / f"{module}.json"
    if not file_path.exists():
        _cache[cache_key] = {}
        return {}

    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
        _cache[cache_key] = data
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.error(
            "Failed to load locale file",
            extra={"locale": locale, "module": module, "path": str(file_path)},
            error_code=ErrorCodes.IO_READ_FAILED,
        )
        _cache[cache_key] = {}
        return {}


def get_text(locale: str | None, module: str, key: str, **kwargs: object) -> str:
    """Look up a translated string by module and key.

    Args:
        locale: User's language code (e.g. "en", "ru"). Falls back to
                DEFAULT_LOCALE when None or when the locale has no
                translation for the requested key.
        module: The locale module name (e.g. "bot", "miniapp", "common").
        key: The dotted key within the module JSON file.
        **kwargs: Interpolation values for ``str.format_map()``.

    Returns:
        The translated string with interpolated values, or the raw key
        if no translation is found.
    """
    locale = locale or DEFAULT_LOCALE

    # Try requested locale first
    strings = _load_module(locale, module)
    text = strings.get(key)

    # Fall back to default locale
    if text is None and locale != DEFAULT_LOCALE:
        strings = _load_module(DEFAULT_LOCALE, module)
        text = strings.get(key)

    if text is None:
        logger.warning(
            "Missing translation key",
            extra={"locale": locale, "module": module, "key": key},
        )
        return key

    if kwargs:
        try:
            text = text.format_map(kwargs)
        except KeyError:
            logger.warning(
                "Missing interpolation variable in translation",
                extra={"locale": locale, "module": module, "key": key},
            )

    return text


@lru_cache(maxsize=1)
def available_locales() -> list[str]:
    """Return a sorted list of available locale codes."""
    if not LOCALES_DIR.exists():
        return [DEFAULT_LOCALE]
    return sorted(
        d.name for d in LOCALES_DIR.iterdir() if d.is_dir()
    )


def clear_cache() -> None:
    """Clear the in-memory translation cache. Useful for testing."""
    _cache.clear()
    available_locales.cache_clear()
