"""Tests for the full conversion pipeline."""

import os
import tempfile
from unittest.mock import AsyncMock, patch

import pytest

from app.services.conversion.fetcher import FetchResult
from app.services.conversion.pipeline import ConversionResult, convert_url


GOOD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Test Article Title</title>
    <meta name="author" content="Pipeline Author">
</head>
<body>
    <article>
        <h1>Test Article Title</h1>
        <p>This is a comprehensive article with enough content to pass validation.
        The article discusses important topics and provides valuable insights for
        readers. Each paragraph adds detail and context, ensuring the readability
        extraction algorithm identifies this as the primary content block. We need
        a good amount of text here to pass the minimum character threshold.</p>
        <p>Here is a second paragraph to reinforce the content density. More text
        helps readability distinguish the article body from navigation and other
        page chrome elements. This paragraph continues with additional context.</p>
    </article>
</body>
</html>
"""


async def test_pipeline_full_flow():
    """End-to-end: URL -> EPUB file created on disk."""
    mock_fetch_result = FetchResult(
        html=GOOD_HTML,
        status_code=200,
        content_type="text/html",
        final_url="https://example.com/article",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch(
            "app.services.conversion.pipeline.fetch_page",
            new_callable=AsyncMock,
            return_value=mock_fetch_result,
        ), patch(
            "app.services.conversion.pipeline.process_images",
            new_callable=AsyncMock,
        ) as mock_images:
            from app.services.conversion.image_processor import ImageProcessingResult

            mock_images.return_value = ImageProcessingResult(
                content_html="<p>Processed content</p>",
                images=[],
            )

            result = await convert_url(
                "https://example.com/article",
                output_dir=tmpdir,
            )

            assert isinstance(result, ConversionResult)
            assert os.path.exists(result.epub_path)
            assert result.epub_path.endswith(".epub")
            assert result.used_playwright is False
            assert result.image_count == 0
            assert result.file_size_bytes > 0


async def test_pipeline_validation_fails_raises():
    """Pipeline raises ValueError when content fails validation."""
    bad_html = "<html><head><title></title></head><body><p>Short</p></body></html>"
    mock_fetch_result = FetchResult(
        html=bad_html,
        status_code=200,
        content_type="text/html",
        final_url="https://example.com/bad",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch(
            "app.services.conversion.pipeline.fetch_page",
            new_callable=AsyncMock,
            return_value=mock_fetch_result,
        ), patch(
            "app.services.conversion.pipeline.settings",
        ) as mock_settings:
            mock_settings.PLAYWRIGHT_ENABLED = False

            with pytest.raises(ValueError, match="validation failed"):
                await convert_url("https://example.com/bad", output_dir=tmpdir)


async def test_pipeline_playwright_fallback():
    """Pipeline triggers Playwright fallback when validation fails and it's enabled."""
    bad_html = "<html><head><title></title></head><body><p>Short</p></body></html>"
    mock_bad_fetch = FetchResult(
        html=bad_html,
        status_code=200,
        content_type="text/html",
        final_url="https://example.com/spa",
    )
    mock_good_fetch = FetchResult(
        html=GOOD_HTML,
        status_code=200,
        content_type="text/html",
        final_url="https://example.com/spa",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch(
            "app.services.conversion.pipeline.fetch_page",
            new_callable=AsyncMock,
            return_value=mock_bad_fetch,
        ), patch(
            "app.services.conversion.pipeline.settings",
        ) as mock_settings, patch(
            "app.services.conversion.browser_fetcher.fetch_with_browser",
            new_callable=AsyncMock,
            return_value=mock_good_fetch,
        ) as mock_browser, patch(
            "app.services.conversion.pipeline.process_images",
            new_callable=AsyncMock,
        ) as mock_images:
            mock_settings.PLAYWRIGHT_ENABLED = True

            from app.services.conversion.image_processor import ImageProcessingResult

            mock_images.return_value = ImageProcessingResult(
                content_html="<p>Browser content</p>",
                images=[],
            )

            result = await convert_url(
                "https://example.com/spa",
                output_dir=tmpdir,
            )

            assert result.used_playwright is True
            mock_browser.assert_called_once()
