"""Playwright browser fallback for JavaScript-heavy pages."""

from dataclasses import dataclass

from logs_flow import create_logger

from app.services.conversion.fetcher import FetchResult

logger = create_logger(service="conversion-browser-fetcher")


async def fetch_with_browser(url: str, timeout: int = 30) -> FetchResult:
    """Fetch a page using headless Chromium via Playwright.

    Used as a fallback when the standard HTTP fetch produces content that
    fails validation (e.g., JavaScript-rendered SPAs, lazy-loaded content).

    Args:
        url: The URL to fetch and render.
        timeout: Page load timeout in seconds.

    Returns:
        FetchResult with rendered HTML content.

    Raises:
        RuntimeError: If Playwright is not installed or browser launch fails.
        playwright.async_api.Error: On page navigation or timeout errors.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is not installed. Run: playwright install chromium"
        ) from exc

    logger.info("Fetching page with browser", extra={"url": url, "timeout": timeout})

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 720},
                java_script_enabled=True,
            )
            page = await context.new_page()

            response = await page.goto(
                url,
                wait_until="networkidle",
                timeout=timeout * 1000,
            )

            # Wait a bit more for any late JS rendering
            await page.wait_for_timeout(1000)

            html = await page.content()
            final_url = page.url
            status_code = response.status if response else 200

            await context.close()
        finally:
            await browser.close()

    html_size = len(html.encode("utf-8"))
    logger.info(
        "Browser fetch complete",
        extra={
            "url": url,
            "final_url": final_url,
            "status_code": status_code,
            "html_size_bytes": html_size,
        },
    )

    return FetchResult(
        html=html,
        status_code=status_code,
        content_type="text/html",
        final_url=final_url,
    )
