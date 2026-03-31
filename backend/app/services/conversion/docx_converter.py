"""Convert DOCX files to Kindle-ready EPUB with images preserved."""

import hashlib
import io
import os

import mammoth
from ebooklib import epub
from logs_flow import create_logger

logger = create_logger(service="conversion-docx")

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


def convert_docx_to_epub(file_bytes: bytes, title: str, output_path: str) -> str:
    """Convert a DOCX file to EPUB, preserving embedded images.

    Uses mammoth to convert DOCX → HTML with image extraction,
    then assembles an EPUB with ebooklib.

    Args:
        file_bytes: Raw DOCX file content.
        title: Title for the EPUB book.
        output_path: Full path for the output EPUB file.

    Returns:
        The output_path where the EPUB was written.
    """
    images: list[tuple[str, str, bytes]] = []  # (filename, content_type, data)

    def handle_image(image):
        """Extract image bytes and return an img tag pointing to images/ folder."""
        with image.open() as img_file:
            image_data = img_file.read()

        ext = image.content_type.split("/")[-1]
        if ext == "jpeg":
            ext = "jpg"
        idx = len(images)
        filename = f"img_{idx:03d}.{ext}"
        images.append((filename, image.content_type, image_data))

        attrs = {"src": f"images/{filename}"}
        if image.alt_text:
            attrs["alt"] = image.alt_text
        return [mammoth.html.element("img", attrs)]

    result = mammoth.convert_to_html(
        io.BytesIO(file_bytes),
        convert_image=handle_image,
    )
    content_html = result.value

    if not content_html or not content_html.strip():
        raise ValueError("mammoth extracted no content from DOCX")

    # Build EPUB
    book = epub.EpubBook()
    book.set_identifier(hashlib.md5(file_bytes[:1000]).hexdigest())
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

    # Embed images
    for filename, content_type, data in images:
        img_item = epub.EpubItem(
            uid=filename.replace(".", "_"),
            file_name=f"images/{filename}",
            media_type=content_type,
            content=data,
        )
        book.add_item(img_item)

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

    # Write EPUB
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    epub.write_epub(output_path, book)

    file_size = os.path.getsize(output_path)
    logger.info(
        "DOCX EPUB built",
        extra={
            "output_path": output_path,
            "title": title,
            "image_count": len(images),
            "file_size_bytes": file_size,
        },
    )

    return output_path
