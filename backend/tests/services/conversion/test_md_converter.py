"""Tests for Markdown to EPUB conversion."""

import os
import tempfile
import zipfile

from app.services.conversion.md_converter import convert_md_to_epub


class TestConvertMdToEpub:
    def test_creates_valid_epub(self):
        md_text = "# Hello World\n\nThis is a test."
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test.epub")
            result = convert_md_to_epub(md_text, "Test Doc", output_path)

            assert result == output_path
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0
            assert zipfile.is_zipfile(output_path)

    def test_epub_contains_title(self):
        md_text = "# My Article\n\nContent here."
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "out.epub")
            convert_md_to_epub(md_text, "My Article", output_path)

            with zipfile.ZipFile(output_path, "r") as zf:
                content = zf.read("EPUB/content.xhtml").decode("utf-8")
                assert "My Article" in content

    def test_epub_renders_markdown_formatting(self):
        md_text = "**bold** and *italic* and `code`"
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "out.epub")
            convert_md_to_epub(md_text, "Formatting Test", output_path)

            with zipfile.ZipFile(output_path, "r") as zf:
                content = zf.read("EPUB/content.xhtml").decode("utf-8")
                assert "<strong>bold</strong>" in content
                assert "<em>italic</em>" in content
                assert "<code>code</code>" in content

    def test_epub_renders_tables(self):
        md_text = "| A | B |\n|---|---|\n| 1 | 2 |"
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "out.epub")
            convert_md_to_epub(md_text, "Table Test", output_path)

            with zipfile.ZipFile(output_path, "r") as zf:
                content = zf.read("EPUB/content.xhtml").decode("utf-8")
                assert "<table>" in content

    def test_epub_renders_fenced_code_blocks(self):
        md_text = "```python\nprint('hello')\n```"
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "out.epub")
            convert_md_to_epub(md_text, "Code Test", output_path)

            with zipfile.ZipFile(output_path, "r") as zf:
                content = zf.read("EPUB/content.xhtml").decode("utf-8")
                assert "print" in content

    def test_epub_has_stylesheet(self):
        md_text = "# Hello"
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "out.epub")
            convert_md_to_epub(md_text, "Style Test", output_path)

            with zipfile.ZipFile(output_path, "r") as zf:
                names = zf.namelist()
                assert any("default.css" in n for n in names)

    def test_creates_output_directory(self):
        md_text = "# Test"
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_path = os.path.join(tmpdir, "sub", "dir", "test.epub")
            convert_md_to_epub(md_text, "Nested Test", nested_path)
            assert os.path.exists(nested_path)
