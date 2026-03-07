"""Tests for the HTTP fetcher."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.conversion.fetcher import FetchResult, fetch_page


def _mock_response(
    status_code: int = 200,
    text: str = "<html></html>",
    content_type: str = "text/html",
    url: str = "https://example.com/article",
):
    """Create a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.text = text
    resp.encoding = "utf-8"
    resp.headers = {"content-type": content_type}
    resp.url = httpx.URL(url)
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"{status_code}", request=MagicMock(), response=resp
        )
    return resp


@pytest.fixture
def mock_html():
    return "<html><head><title>Test</title></head><body><p>Hello world</p></body></html>"


async def test_fetch_page_success(mock_html):
    """fetch_page returns FetchResult with correct fields on 200."""
    mock_resp = _mock_response(text=mock_html)

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.conversion.fetcher.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_page("https://example.com/article")

    assert isinstance(result, FetchResult)
    assert result.html == mock_html
    assert result.status_code == 200
    assert "text/html" in result.content_type


async def test_fetch_page_raises_on_404():
    """fetch_page raises HTTPStatusError on non-2xx."""
    mock_resp = _mock_response(status_code=404)

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.conversion.fetcher.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(httpx.HTTPStatusError):
            await fetch_page("https://example.com/missing")
