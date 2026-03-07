"""Orchestrates the full conversion pipeline: fetch -> extract -> validate -> images -> EPUB."""

import os
from dataclasses import dataclass

from logs_flow import create_logger

from app.core.config import settings
from app.services.conversion.epub_builder import build_epub, slugify
from app.services.conversion.extractor import extract_article
from app.services.conversion.fetcher import fetch_page
from app.services.conversion.image_processor import process_images
from app.services.conversion.validator import validate_content

logger = create_logger(service="conversion-pipeline")


@dataclass
class ConversionResult:
    epub_path: str
    title: str
    author: str
    image_count: int
    file_size_bytes: int
    used_playwright: bool


async def convert_url(
    url: str,
    output_dir: str,
    grayscale: bool = True,
    max_image_width: int = 1200,
    image_quality: int = 80,
    request_timeout: float = 20.0,
) -> ConversionResult:
    """Run the full URL-to-EPUB conversion pipeline.

    Pipeline steps:
        1. Fetch HTML from URL
        2. Extract article content and metadata
        3. Validate content quality
        4. If validation fails and Playwright is enabled, retry with browser
        5. Download and optimize images
        6. Build EPUB file

    Args:
        url: The article URL to convert.
        output_dir: Directory to write the EPUB file.
        grayscale: Convert images to grayscale for e-readers.
        max_image_width: Maximum image width in pixels.
        image_quality: JPEG compression quality (1-100).
        request_timeout: HTTP request timeout in seconds.

    Returns:
        ConversionResult with EPUB path and metadata.

    Raises:
        httpx.HTTPStatusError: On fetch failure (non-2xx).
        httpx.RequestError: On connection/timeout errors.
        ValueError: If content validation fails after all attempts.
    """
    logger.info("Starting conversion", extra={"url": url})

    # 1. Fetch
    fetch_result = await fetch_page(url, timeout=request_timeout)
    logger.info(
        "Fetch complete",
        extra={"url": url, "html_size_kb": len(fetch_result.html) // 1024},
    )

    # 2. Extract
    article = extract_article(fetch_result.html, fetch_result.final_url)

    # 3. Validate
    used_playwright = False
    validation = validate_content(article.title, article.content_html, article.source_url)

    if not validation.passed:
        # 3a. Try Playwright fallback if enabled
        if settings.PLAYWRIGHT_ENABLED:
            logger.info(
                "HTTP fetch failed validation, trying Playwright fallback",
                extra={"url": url, "validation_reason": validation.reason},
            )

            from app.services.conversion.browser_fetcher import fetch_with_browser

            browser_result = await fetch_with_browser(url, timeout=30)
            article = extract_article(browser_result.html, browser_result.final_url)

            validation = validate_content(
                article.title, article.content_html, article.source_url
            )
            if not validation.passed:
                raise ValueError(
                    f"Content validation failed after Playwright fallback: {validation.reason}"
                )

            used_playwright = True
            logger.info(
                "Playwright fallback succeeded",
                extra={"url": url, "title": article.title},
            )
        else:
            raise ValueError(f"Content validation failed: {validation.reason}")

    # 4. Process images
    image_result = await process_images(
        article.content_html,
        article.source_url,
        grayscale=grayscale,
        max_width=max_image_width,
        quality=image_quality,
        timeout=request_timeout,
    )

    # 5. Build EPUB
    os.makedirs(output_dir, exist_ok=True)
    slug = slugify(article.title) or "article"
    epub_filename = f"{slug}.epub"
    epub_path = os.path.join(output_dir, epub_filename)

    build_epub(article, image_result.content_html, image_result.images, epub_path)

    file_size = os.path.getsize(epub_path)

    logger.info(
        "Conversion complete",
        extra={
            "url": url,
            "title": article.title,
            "epub_path": epub_path,
            "image_count": len(image_result.images),
            "file_size_bytes": file_size,
            "used_playwright": used_playwright,
        },
    )

    return ConversionResult(
        epub_path=epub_path,
        title=article.title,
        author=article.author,
        image_count=len(image_result.images),
        file_size_bytes=file_size,
        used_playwright=used_playwright,
    )
