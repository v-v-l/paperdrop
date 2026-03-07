"""Tests for URL extraction and validation utilities."""

from app.services.telegram.url_utils import extract_urls, is_valid_url


class TestExtractUrls:
    def test_single_url(self):
        text = "Check out https://example.com/article"
        urls = extract_urls(text)
        assert urls == ["https://example.com/article"]

    def test_multiple_urls(self):
        text = "Visit https://a.com and http://b.com/page for more"
        urls = extract_urls(text)
        assert len(urls) == 2
        assert "https://a.com" in urls
        assert "http://b.com/page" in urls

    def test_url_with_query_params(self):
        text = "Link: https://example.com/search?q=test&lang=en"
        urls = extract_urls(text)
        assert len(urls) == 1
        assert "q=test" in urls[0]

    def test_no_urls(self):
        text = "This message has no links at all"
        assert extract_urls(text) == []

    def test_empty_text(self):
        assert extract_urls("") == []
        assert extract_urls(None) == []

    def test_ftp_not_extracted(self):
        text = "ftp://files.example.com/data"
        assert extract_urls(text) == []

    def test_url_in_forwarded_message_text(self):
        text = "Forwarded message:\nhttps://example.com/forwarded-article\n-- Original sender"
        urls = extract_urls(text)
        assert urls == ["https://example.com/forwarded-article"]


class TestIsValidUrl:
    def test_valid_https(self):
        assert is_valid_url("https://example.com/article") is True

    def test_valid_http(self):
        assert is_valid_url("http://example.com") is True

    def test_rejects_ftp(self):
        assert is_valid_url("ftp://example.com") is False

    def test_rejects_no_scheme(self):
        assert is_valid_url("example.com") is False

    def test_rejects_localhost(self):
        assert is_valid_url("http://localhost/admin") is False

    def test_rejects_loopback(self):
        assert is_valid_url("http://127.0.0.1/secret") is False

    def test_rejects_zero_address(self):
        assert is_valid_url("http://0.0.0.0/") is False

    def test_rejects_no_dot_in_host(self):
        assert is_valid_url("http://intranet/page") is False

    def test_rejects_empty_string(self):
        assert is_valid_url("") is False

    def test_rejects_garbage(self):
        assert is_valid_url("not-a-url-at-all") is False
