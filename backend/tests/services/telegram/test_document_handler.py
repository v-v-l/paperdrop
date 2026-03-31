"""Tests for EPUB/PDF/MD file validation in the document handler."""

import io
import zipfile

from app.services.telegram.handlers import _validate_docx, _validate_epub, _validate_md, _validate_pdf


def _make_epub(include_mimetype=True, include_drm=False):
    """Create a minimal EPUB ZIP in memory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        if include_mimetype:
            zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("META-INF/container.xml", "<container/>")
        if include_drm:
            zf.writestr(
                "META-INF/encryption.xml",
                '<encryption><EncryptedData/></encryption>',
            )
        zf.writestr("OEBPS/content.opf", "<package/>")
    return buf.getvalue()


def test_validate_epub_valid():
    epub_bytes = _make_epub()
    assert _validate_epub(epub_bytes) is None


def test_validate_epub_not_a_zip():
    assert _validate_epub(b"not a zip file") == "epub_invalid_format"


def test_validate_epub_no_mimetype():
    epub_bytes = _make_epub(include_mimetype=False)
    assert _validate_epub(epub_bytes) == "epub_invalid_format"


def test_validate_epub_drm_protected():
    epub_bytes = _make_epub(include_drm=True)
    assert _validate_epub(epub_bytes) == "epub_drm_protected"


def test_validate_pdf_valid():
    pdf_bytes = b"%PDF-1.4 some content"
    assert _validate_pdf(pdf_bytes) is None


def test_validate_pdf_invalid():
    assert _validate_pdf(b"not a pdf") == "pdf_invalid_format"


def test_validate_pdf_empty():
    assert _validate_pdf(b"") == "pdf_invalid_format"


def test_validate_md_valid():
    md_bytes = "# Hello\n\nSome **bold** text.".encode("utf-8")
    assert _validate_md(md_bytes) is None


def test_validate_md_empty():
    assert _validate_md(b"") == "md_invalid_format"


def test_validate_md_whitespace_only():
    assert _validate_md(b"   \n\n  ") == "md_invalid_format"


def test_validate_md_not_utf8():
    # Invalid UTF-8 byte sequence
    assert _validate_md(b"\xff\xfe\x00\x01") == "md_invalid_format"


def test_validate_md_plain_text():
    """Plain text without Markdown formatting is still valid."""
    assert _validate_md(b"Just some plain text") is None


def _make_docx():
    """Create a minimal DOCX ZIP in memory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", '<Types/>')
        zf.writestr("word/document.xml", '<document/>')
    return buf.getvalue()


def test_validate_docx_valid():
    assert _validate_docx(_make_docx()) is None


def test_validate_docx_not_a_zip():
    assert _validate_docx(b"not a zip") == "docx_invalid_format"


def test_validate_docx_zip_without_content_types():
    """A ZIP file that isn't a DOCX (missing [Content_Types].xml)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("random.txt", "hello")
    assert _validate_docx(buf.getvalue()) == "docx_invalid_format"


def test_validate_docx_empty():
    assert _validate_docx(b"") == "docx_invalid_format"
