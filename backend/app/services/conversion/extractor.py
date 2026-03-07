"""Readability-based article extraction and metadata parsing."""

from dataclasses import dataclass

from bs4 import BeautifulSoup
from logs_flow import create_logger
from readability import Document

logger = create_logger(service="conversion-extractor")


@dataclass
class ArticleData:
    title: str
    content_html: str
    author: str
    date: str
    source_url: str


def clean_title(title: str) -> str:
    """Strip site name suffixes like 'Article | Site' or 'Article -- Site'."""
    for sep in [" | ", " \\ ", " — ", " – ", " - "]:
        if sep in title:
            parts = title.rsplit(sep, 1)
            title = max(parts, key=len).strip()
    return title


def _extract_meta(soup: BeautifulSoup, target_names: set[str]) -> str:
    """Extract content from the first matching meta tag."""
    for meta in soup.find_all("meta"):
        name = meta.get("name", "").lower()
        prop = meta.get("property", "").lower()
        if name in target_names or prop in target_names:
            return meta.get("content", "")
    return ""


def extract_article(html: str, url: str) -> ArticleData:
    """Use readability to extract clean article content and metadata.

    Args:
        html: Raw HTML string.
        url: Source URL (used for relative link resolution).

    Returns:
        ArticleData with extracted title, content, author, date, and source URL.
    """
    doc = Document(html, url=url)
    title = clean_title(doc.title())
    content_html = doc.summary()

    soup = BeautifulSoup(html, "lxml")

    author = _extract_meta(soup, {"author", "article:author"})
    date = _extract_meta(
        soup,
        {"date", "article:published_time", "publisheddate", "og:article:published_time"},
    )

    logger.info(
        "Article extracted",
        extra={
            "title": title,
            "author": author,
            "has_date": bool(date),
            "content_length": len(content_html),
        },
    )

    return ArticleData(
        title=title,
        content_html=content_html,
        author=author,
        date=date,
        source_url=url,
    )
