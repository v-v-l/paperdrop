"""Tests for the Kindle email sender service."""

import os
import tempfile
from unittest.mock import AsyncMock, patch

import pytest

from app.services.email.kindle_sender import send_to_kindle


@pytest.fixture
def epub_file():
    """Create a temporary EPUB file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as f:
        f.write(b"fake epub content")
        path = f.name
    yield path
    if os.path.exists(path):
        os.remove(path)


async def test_send_to_kindle_skips_when_no_api_key(epub_file):
    """Should return False when RESEND_API_KEY is not configured."""
    with patch("app.services.email.kindle_sender.settings") as mock_settings:
        mock_settings.RESEND_API_KEY = ""
        result = await send_to_kindle("test@kindle.com", epub_file, "Test Article")
    assert result is False


async def test_send_to_kindle_success(epub_file):
    """Should return True when Resend API returns 200."""
    mock_response = AsyncMock()
    mock_response.raise_for_status = lambda: None

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.services.email.kindle_sender.settings") as mock_settings,
        patch("app.services.email.kindle_sender.httpx.AsyncClient", return_value=mock_client),
    ):
        mock_settings.RESEND_API_KEY = "re_test_123"
        mock_settings.SENDER_EMAIL = "send@test.com"
        result = await send_to_kindle("user@kindle.com", epub_file, "Test Article")

    assert result is True
    mock_client.post.assert_called_once()
    call_kwargs = mock_client.post.call_args
    assert call_kwargs[1]["json"]["to"] == ["user@kindle.com"]
    assert call_kwargs[1]["json"]["from"] == "send@test.com"


async def test_send_to_kindle_api_error(epub_file):
    """Should return False when Resend API returns an error."""
    mock_response = AsyncMock()
    mock_response.raise_for_status = lambda: (_ for _ in ()).throw(
        Exception("API error")
    )

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.services.email.kindle_sender.settings") as mock_settings,
        patch("app.services.email.kindle_sender.httpx.AsyncClient", return_value=mock_client),
    ):
        mock_settings.RESEND_API_KEY = "re_test_123"
        mock_settings.SENDER_EMAIL = "send@test.com"
        result = await send_to_kindle("user@kindle.com", epub_file, "Test Article")

    assert result is False
