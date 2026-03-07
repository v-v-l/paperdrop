"""Tests for EPUB assembly."""

import os
import tempfile
import zipfile

from app.services.conversion.epub_builder import build_epub, slugify
from app.services.conversion.extractor import ArticleData
from app.services.conversion.image_processor import ProcessedImage


class TestSlugify:
    def test_basic_slug(self):
        assert slugify("Hello World") == "hello-world"

    def test_special_characters(self):
        assert slugify("What's New? (2025)") == "whats-new-2025"

    def test_max_length(self):
        result = slugify("A" * 100, max_len=10)
        assert len(result) <= 10

    def test_empty_string(self):
        assert slugify("") == ""


class TestBuildEpub:
    def test_creates_valid_epub_file(self):
        article = ArticleData(
            title="Test Article",
            content_html="<p>This is test content for the EPUB builder.</p>",
            author="Test Author",
            date="2025-01-15",
            source_url="https://example.com/test",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test.epub")
            result = build_epub(article, article.content_html, [], output_path)

            assert result == output_path
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0

            # EPUB is a ZIP file -- verify it's valid
            assert zipfile.is_zipfile(output_path)

            with zipfile.ZipFile(output_path, "r") as zf:
                names = zf.namelist()
                # ebooklib puts files under EPUB/ prefix
                assert any("content.xhtml" in n for n in names)
                assert any("default.css" in n for n in names)

    def test_epub_contains_title_and_author(self):
        article = ArticleData(
            title="My Great Article",
            content_html="<p>Content goes here</p>",
            author="Jane Smith",
            date="",
            source_url="https://example.com",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "out.epub")
            build_epub(article, article.content_html, [], output_path)

            with zipfile.ZipFile(output_path, "r") as zf:
                content = zf.read("EPUB/content.xhtml").decode("utf-8")
                assert "My Great Article" in content
                assert "Jane Smith" in content

    def test_epub_embeds_images(self):
        article = ArticleData(
            title="With Images",
            content_html='<p>Text</p><img src="img_000_abc.jpg"/>',
            author="",
            date="",
            source_url="https://example.com",
        )
        images = [
            ProcessedImage(
                filename="img_000_abc.jpg",
                data=b"\xff\xd8\xff\xe0" + b"\x00" * 100,  # Fake JPEG bytes
                media_type="image/jpeg",
            )
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "out.epub")
            build_epub(article, article.content_html, images, output_path)

            with zipfile.ZipFile(output_path, "r") as zf:
                names = zf.namelist()
                assert any("img_000_abc" in n for n in names)

    def test_untitled_article(self):
        article = ArticleData(
            title="",
            content_html="<p>Content</p>",
            author="",
            date="",
            source_url="https://example.com",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "out.epub")
            build_epub(article, article.content_html, [], output_path)

            with zipfile.ZipFile(output_path, "r") as zf:
                content = zf.read("EPUB/content.xhtml").decode("utf-8")
                assert "Untitled Article" in content
