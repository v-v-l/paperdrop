"""Content quality validation for extracted articles."""

import urllib.parse
from dataclasses import dataclass

from bs4 import BeautifulSoup
from logs_flow import create_logger

logger = create_logger(service="conversion-validator")

MIN_CONTENT_LENGTH = 200


@dataclass
class ValidationResult:
    passed: bool
    reason: str


def validate_content(title: str, content_html: str, source_url: str) -> ValidationResult:
    """Validate extracted article content quality.

    Checks:
        - Content is not empty.
        - Extracted text length > 200 characters.
        - Title was extracted (not just the domain name).

    Args:
        title: Extracted article title.
        content_html: Extracted HTML content.
        source_url: Original URL (used to detect domain-only titles).

    Returns:
        ValidationResult with passed status and reason.
    """
    # Check content is not empty
    if not content_html or not content_html.strip():
        logger.warning("Validation failed: empty content", extra={"url": source_url})
        return ValidationResult(passed=False, reason="Extracted content is empty")

    # Check text length (strip HTML tags)
    soup = BeautifulSoup(content_html, "lxml")
    text = soup.get_text(separator=" ", strip=True)

    if len(text) < MIN_CONTENT_LENGTH:
        logger.warning(
            "Validation failed: content too short",
            extra={"url": source_url, "text_length": len(text)},
        )
        return ValidationResult(
            passed=False,
            reason=f"Extracted text too short ({len(text)} chars, minimum {MIN_CONTENT_LENGTH})",
        )

    # Check title is not just the domain name
    if not title or not title.strip():
        logger.warning("Validation failed: no title", extra={"url": source_url})
        return ValidationResult(passed=False, reason="No title extracted")

    parsed_url = urllib.parse.urlparse(source_url)
    domain = parsed_url.netloc.lower().removeprefix("www.")
    title_lower = title.strip().lower()

    if title_lower == domain or title_lower == parsed_url.netloc.lower():
        logger.warning(
            "Validation failed: title is just domain",
            extra={"url": source_url, "title": title},
        )
        return ValidationResult(
            passed=False,
            reason=f"Title is just the domain name: '{title}'",
        )

    logger.info(
        "Content validation passed",
        extra={"url": source_url, "title": title, "text_length": len(text)},
    )
    return ValidationResult(passed=True, reason="OK")
