"""Convert Markdown text to a Kindle-ready EPUB file."""

import hashlib
import os

import markdown
from ebooklib import epub
from logs_flow import create_logger

logger = create_logger(service="conversion-md")

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
pre {
    background: #f4f4f4;
    padding: 1em;
    overflow-x: auto;
    font-size: 0.9em;
}
code {
    font-family: monospace;
    font-size: 0.9em;
}
table {
    border-collapse: collapse;
    margin: 1em 0;
    width: 100%;
}
th, td {
    border: 1px solid #ccc;
    padding: 0.5em;
    text-align: left;
}
th { background: #f4f4f4; }
"""

MD_EXTENSIONS = [
    "tables",
    "fenced_code",
    "codehilite",
    "toc",
    "smarty",
    "sane_lists",
]


def convert_md_to_epub(md_text: str, title: str, output_path: str) -> str:
    """Convert Markdown text to an EPUB file.

    Args:
        md_text: Raw Markdown content.
        title: Title for the EPUB book.
        output_path: Full path for the output EPUB file.

    Returns:
        The output_path where the EPUB was written.
    """
    md = markdown.Markdown(extensions=MD_EXTENSIONS)
    content_html = md.convert(md_text)

    book = epub.EpubBook()
    book.set_identifier(hashlib.md5(md_text[:1000].encode()).hexdigest())
    book.set_title(title)
    book.set_language("en")

    # Stylesheet
    style = epub.EpubItem(
        uid="style",
        file_name="style/default.css",
        media_type="text/css",
        content=KINDLE_CSS.encode("utf-8"),
    )
    book.add_item(style)

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
        "Markdown EPUB built",
        extra={
            "output_path": output_path,
            "title": title,
            "file_size_bytes": file_size,
        },
    )

    return output_path
