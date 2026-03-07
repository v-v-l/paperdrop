"""Tests for content quality validation."""

from app.services.conversion.validator import ValidationResult, validate_content


class TestValidateContent:
    def test_valid_content_passes(self):
        content = "<p>" + "This is meaningful article content. " * 20 + "</p>"
        result = validate_content("Good Title", content, "https://example.com/article")

        assert result.passed is True
        assert result.reason == "OK"

    def test_empty_content_fails(self):
        result = validate_content("Title", "", "https://example.com")
        assert result.passed is False
        assert "empty" in result.reason.lower()

    def test_whitespace_only_content_fails(self):
        result = validate_content("Title", "   \n\t  ", "https://example.com")
        assert result.passed is False
        assert "empty" in result.reason.lower()

    def test_short_content_fails(self):
        result = validate_content("Title", "<p>Too short</p>", "https://example.com")
        assert result.passed is False
        assert "short" in result.reason.lower()

    def test_no_title_fails(self):
        content = "<p>" + "Valid content " * 50 + "</p>"
        result = validate_content("", content, "https://example.com")
        assert result.passed is False
        assert "title" in result.reason.lower()

    def test_domain_only_title_fails(self):
        content = "<p>" + "Valid content " * 50 + "</p>"
        result = validate_content("example.com", content, "https://example.com/article")
        assert result.passed is False
        assert "domain" in result.reason.lower()

    def test_www_domain_title_fails(self):
        content = "<p>" + "Valid content " * 50 + "</p>"
        result = validate_content(
            "www.example.com", content, "https://www.example.com/article"
        )
        assert result.passed is False
        assert "domain" in result.reason.lower()

    def test_content_length_boundary(self):
        """Content of exactly 200 chars should pass."""
        # Create content with exactly 200 chars of text
        text = "a" * 200
        content = f"<p>{text}</p>"
        result = validate_content("Title", content, "https://example.com")
        assert result.passed is True
