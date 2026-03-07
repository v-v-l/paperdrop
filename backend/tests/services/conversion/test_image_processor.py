"""Tests for image processing (resize, grayscale, optimize)."""

import io

from PIL import Image

from app.services.conversion.image_processor import (
    _optimize_image,
    resolve_url,
)


def _make_test_image(width: int = 200, height: int = 100, mode: str = "RGB") -> bytes:
    """Create a simple test image as bytes."""
    img = Image.new(mode, (width, height), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestResolveUrl:
    def test_absolute_url(self):
        assert resolve_url("https://example.com", "https://cdn.example.com/img.jpg") == "https://cdn.example.com/img.jpg"

    def test_protocol_relative(self):
        assert resolve_url("https://example.com", "//cdn.example.com/img.jpg") == "https://cdn.example.com/img.jpg"

    def test_root_relative(self):
        assert resolve_url("https://example.com/page", "/images/photo.jpg") == "https://example.com/images/photo.jpg"

    def test_relative_path(self):
        result = resolve_url("https://example.com/article/page.html", "images/photo.jpg")
        assert result == "https://example.com/article/images/photo.jpg"

    def test_data_url_returns_empty(self):
        assert resolve_url("https://example.com", "data:image/png;base64,abc") == ""

    def test_empty_src_returns_empty(self):
        assert resolve_url("https://example.com", "") == ""


class TestOptimizeImage:
    def test_returns_jpeg_bytes(self):
        raw = _make_test_image()
        result_bytes, ext = _optimize_image(raw, grayscale=False, max_width=1200, quality=80)

        assert ext == ".jpg"
        assert len(result_bytes) > 0

        # Verify it's a valid JPEG
        img = Image.open(io.BytesIO(result_bytes))
        assert img.format == "JPEG"

    def test_resize_when_too_wide(self):
        raw = _make_test_image(width=2000, height=1000)
        result_bytes, _ = _optimize_image(raw, grayscale=False, max_width=800, quality=80)

        img = Image.open(io.BytesIO(result_bytes))
        assert img.width == 800
        assert img.height == 400  # Proportional resize

    def test_no_resize_when_under_max(self):
        raw = _make_test_image(width=500, height=300)
        result_bytes, _ = _optimize_image(raw, grayscale=False, max_width=1200, quality=80)

        img = Image.open(io.BytesIO(result_bytes))
        assert img.width == 500
        assert img.height == 300

    def test_grayscale_conversion(self):
        raw = _make_test_image()
        result_bytes, _ = _optimize_image(raw, grayscale=True, max_width=1200, quality=80)

        img = Image.open(io.BytesIO(result_bytes))
        assert img.mode == "L"

    def test_rgba_input_handled(self):
        raw = _make_test_image(mode="RGBA")
        result_bytes, _ = _optimize_image(raw, grayscale=False, max_width=1200, quality=80)

        img = Image.open(io.BytesIO(result_bytes))
        assert img.format == "JPEG"
