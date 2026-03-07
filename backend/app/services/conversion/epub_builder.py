"""EPUB assembly from extracted article content and images."""

import hashlib
import os
import re

from ebooklib import epub
from logs_flow import create_logger

from app.services.conversion.extractor import ArticleData
from app.services.conversion.image_processor import ProcessedImage

logger = create_logger(service="conversion-epub")

KINDLE_CSS = """
body {
    font-family: Georgia, serif;
    line-height: 1.6;
    margin: 1em;
    color: #000;
}
h1, h2, h3, h4 { margin-top: 1em; margin-bottom: 0.5em; }
img {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 1em auto;
}
p { margin: 0.5em 0; text-indent: 0; }
blockquote {
    margin: 1em 2em;
    padding-left: 1em;
    border-left: 3px solid #666;
    font-style: italic;
}
a { color: #333; text-decoration: underline; }
.source-info {
    font-size: 0.85em;
    color: #666;
    margin-bottom: 2em;
    border-bottom: 1px solid #ccc;
    padding-bottom: 1em;
}
"""


def slugify(text: str, max_len: int = 60) -> str:
    """Convert text to a URL/filename-safe slug."""
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_-]+", "-", text).strip("-")
    return text[:max_len].rstrip("-")


def build_epub(
    article: ArticleData,
    content_html: str,
    images: list[ProcessedImage],
    output_path: str,
) -> str:
    """Assemble an EPUB file with article content and embedded images.

    Args:
        article: Extracted article metadata.
        content_html: Processed HTML with local image references.
        images: List of processed images to embed.
        output_path: Full path for the output EPUB file.

    Returns:
        The output_path where the EPUB was written.
    """
    book = epub.EpubBook()

    title = article.title or "Untitled Article"
    book.set_identifier(hashlib.md5(article.source_url.encode()).hexdigest())
    book.set_title(title)
    book.set_language("en")
    if article.author:
        book.add_author(article.author)
    book.add_metadata("DC", "source", article.source_url)

    # Stylesheet
    style = epub.EpubItem(
        uid="style",
        file_name="style/default.css",
        media_type="text/css",
        content=KINDLE_CSS.encode("utf-8"),
    )
    book.add_item(style)

    # Embed images
    for img in images:
        img_item = epub.EpubItem(
            uid=img.filename.replace(".", "_"),
            file_name=f"images/{img.filename}",
            media_type=img.media_type,
            content=img.data,
        )
        book.add_item(img_item)

    # Fix image paths in HTML to point to images/ folder
    content_html = content_html.replace('src="img_', 'src="images/img_')

    # Build source info header
    source_info = '<div class="source-info">'
    if article.author:
        source_info += f"<strong>{article.author}</strong><br/>"
    if article.date:
        source_info += f"{article.date}<br/>"
    source_info += f"Source: {article.source_url}</div>"

    # Chapter
    chapter = epub.EpubHtml(
        title=title,
        file_name="content.xhtml",
        lang="en",
    )
    chapter.content = f"""
    <html>
    <head><title>{title}</title></head>
    <body>
        <h1>{title}</h1>
        {source_info}
        {content_html}
    </body>
    </html>
    """
    chapter.add_item(style)
    book.add_item(chapter)

    # Table of contents and spine
    book.toc = [chapter]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", chapter]

    # Write EPUB file
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    epub.write_epub(output_path, book)

    file_size = os.path.getsize(output_path)
    logger.info(
        "EPUB built",
        extra={
            "output_path": output_path,
            "title": title,
            "image_count": len(images),
            "file_size_bytes": file_size,
        },
    )

    return output_path
