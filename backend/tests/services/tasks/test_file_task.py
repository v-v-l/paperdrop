"""Tests for file_task helpers — scanned-PDF text-coverage detection."""

import httpx

from app.services.tasks.file_task import _text_coverage


def test_coverage_scanned_pdf_is_zero():
    """Image-only PDF: no page has text → coverage 0.0."""
    headers = httpx.Headers({"X-Pages-Processed": "3", "X-Pages-With-Text": "0"})
    assert _text_coverage(headers) == 0.0


def test_coverage_text_pdf_is_full():
    """Normal PDF: every page has text → coverage 1.0."""
    headers = httpx.Headers({"X-Pages-Processed": "10", "X-Pages-With-Text": "10"})
    assert _text_coverage(headers) == 1.0


def test_coverage_partial():
    """Mixed PDF returns the exact ratio."""
    headers = httpx.Headers({"X-Pages-Processed": "4", "X-Pages-With-Text": "3"})
    assert _text_coverage(headers) == 0.75


def test_coverage_missing_headers_returns_none():
    """Older converter / vision mode omits the header → None (skip fallback)."""
    assert _text_coverage(httpx.Headers({})) is None


def test_coverage_defaults_with_text_to_processed():
    """If only X-Pages-Processed is present, assume full coverage (no fallback)."""
    headers = httpx.Headers({"X-Pages-Processed": "5"})
    assert _text_coverage(headers) == 1.0


def test_coverage_zero_pages_returns_none():
    """Guard against division by zero when the converter reports 0 pages."""
    headers = httpx.Headers({"X-Pages-Processed": "0", "X-Pages-With-Text": "0"})
    assert _text_coverage(headers) is None


def test_coverage_malformed_header_returns_none():
    """Non-numeric header values are tolerated, not fatal."""
    headers = httpx.Headers({"X-Pages-Processed": "lots", "X-Pages-With-Text": "0"})
    assert _text_coverage(headers) is None
