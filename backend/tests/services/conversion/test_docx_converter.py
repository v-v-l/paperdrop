"""Tests for DOCX to EPUB conversion via mammoth."""

import io
import os
import tempfile
import zipfile

import pytest

from app.services.conversion.docx_converter import convert_docx_to_epub


def _make_real_docx(include_image=False):
    """Create a minimal but valid DOCX for mammoth.

    A DOCX is an Open XML ZIP with specific structure. This creates
    the bare minimum that mammoth can parse.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        content_types = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        )
        if include_image:
            content_types += '<Default Extension="png" ContentType="image/png"/>'
        content_types += "</Types>"
        zf.writestr("[Content_Types].xml", content_types)

        doc_rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        )
        if include_image:
            doc_rels += (
                '<Relationship Id="rId10" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
                'Target="media/image1.png"/>'
            )
        doc_rels += "</Relationships>"

        zf.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="word/document.xml"/>'
            "</Relationships>",
        )

        # Build document body
        body = (
            "<w:p><w:pPr><w:pStyle w:val='Heading1'/></w:pPr>"
            "<w:r><w:t>Test Heading</w:t></w:r></w:p>"
            "<w:p><w:r><w:t>This is a test paragraph from a DOCX file.</w:t></w:r></w:p>"
        )
        if include_image:
            body += (
                '<w:p><w:r><w:drawing>'
                '<wp:inline xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">'
                '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
                '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
                '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
                '<pic:blipFill><a:blip r:embed="rId10" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/>'
                '</pic:blipFill>'
                '</pic:pic></a:graphicData></a:graphic></wp:inline>'
                '</w:drawing></w:r></w:p>'
            )

        zf.writestr(
            "word/document.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body>{body}</w:body>"
            "</w:document>",
        )
        zf.writestr("word/_rels/document.xml.rels", doc_rels)

        if include_image:
            # 1x1 red PNG
            png_bytes = (
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
                b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
                b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
                b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
            )
            zf.writestr("word/media/image1.png", png_bytes)

    return buf.getvalue()


class TestConvertDocxToEpub:
    def test_creates_valid_epub(self):
        docx_bytes = _make_real_docx()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test.epub")
            result = convert_docx_to_epub(docx_bytes, "Test Doc", output_path)

            assert result == output_path
            assert os.path.exists(output_path)
            assert zipfile.is_zipfile(output_path)

    def test_epub_contains_docx_content(self):
        docx_bytes = _make_real_docx()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "out.epub")
            convert_docx_to_epub(docx_bytes, "My Word Doc", output_path)

            with zipfile.ZipFile(output_path, "r") as zf:
                content = zf.read("EPUB/content.xhtml").decode("utf-8")
                assert "test paragraph" in content.lower()

    def test_epub_preserves_images(self):
        docx_bytes = _make_real_docx(include_image=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "out.epub")
            convert_docx_to_epub(docx_bytes, "With Image", output_path)

            with zipfile.ZipFile(output_path, "r") as zf:
                names = zf.namelist()
                assert any("img_000" in n for n in names)
                content = zf.read("EPUB/content.xhtml").decode("utf-8")
                assert "images/img_000" in content

    def test_epub_has_stylesheet(self):
        docx_bytes = _make_real_docx()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "out.epub")
            convert_docx_to_epub(docx_bytes, "Style Test", output_path)

            with zipfile.ZipFile(output_path, "r") as zf:
                names = zf.namelist()
                assert any("default.css" in n for n in names)

    def test_empty_docx_raises(self):
        """A DOCX with no text content should raise ValueError."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(
                "[Content_Types].xml",
                '<?xml version="1.0"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Override PartName="/word/document.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                "</Types>",
            )
            zf.writestr(
                "_rels/.rels",
                '<?xml version="1.0"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
                'Target="word/document.xml"/>'
                "</Relationships>",
            )
            zf.writestr(
                "word/document.xml",
                '<?xml version="1.0"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                "<w:body/>"
                "</w:document>",
            )
            zf.writestr(
                "word/_rels/document.xml.rels",
                '<?xml version="1.0"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                "</Relationships>",
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "out.epub")
            with pytest.raises(ValueError, match="no content"):
                convert_docx_to_epub(buf.getvalue(), "Empty", output_path)
