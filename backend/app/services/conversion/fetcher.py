"""Async HTTP fetcher with browser User-Agent."""

from dataclasses import dataclass

import httpx
from logs_flow import create_logger

logger = create_logger(service="conversion-fetcher")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class FetchResult:
    html: str
    status_code: int
    content_type: str
    final_url: str


async def fetch_page(
    url: str,
    timeout: float = 20.0,
    user_agent: str = DEFAULT_USER_AGENT,
) -> FetchResult:
    """Fetch raw HTML from URL using httpx with browser User-Agent.

    Args:
        url: The URL to fetch.
        timeout: Request timeout in seconds.
        user_agent: User-Agent header value.

    Returns:
        FetchResult with HTML content and response metadata.

    Raises:
        httpx.HTTPStatusError: On non-2xx response.
        httpx.RequestError: On connection/timeout errors.
    """
    headers = {"User-Agent": user_agent}

    logger.info("Fetching page", extra={"url": url})

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(timeout),
    ) as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()

        # Determine encoding like requests' apparent_encoding
        encoding = response.encoding or "utf-8"
        html = response.text

        content_type = response.headers.get("content-type", "")
        final_url = str(response.url)

        logger.info(
            "Page fetched successfully",
            extra={
                "url": url,
                "final_url": final_url,
                "status_code": response.status_code,
                "html_size_bytes": len(html.encode("utf-8")),
            },
        )

        return FetchResult(
            html=html,
            status_code=response.status_code,
            content_type=content_type,
            final_url=final_url,
        )
