"""URL extraction and validation utilities for the Telegram bot."""

import re
from urllib.parse import urlparse

# Regex pattern to extract URLs from text.
# Matches http:// and https:// URLs with common path/query/fragment characters.
_URL_PATTERN = re.compile(
    r"https?://"
    r"[a-zA-Z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+"
)


def extract_urls(text: str) -> list[str]:
    """Extract all URLs from the given text.

    Args:
        text: Message text that may contain URLs.

    Returns:
        List of extracted URL strings.
    """
    if not text:
        return []
    return _URL_PATTERN.findall(text)


def is_valid_url(url: str) -> bool:
    """Validate that a URL is suitable for conversion.

    Checks:
        - Scheme is http or https
        - Hostname is present and not localhost / 127.0.0.1

    Args:
        url: URL string to validate.

    Returns:
        True if the URL is valid for conversion.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    if parsed.scheme not in ("http", "https"):
        return False

    hostname = parsed.hostname
    if not hostname:
        return False

    # Reject localhost and loopback addresses
    blocked_hosts = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
    if hostname in blocked_hosts:
        return False

    # Must have a dot in the hostname (basic domain validation)
    if "." not in hostname:
        return False

    return True
