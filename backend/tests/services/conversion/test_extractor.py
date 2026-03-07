"""Tests for article extraction."""

from app.services.conversion.extractor import ArticleData, clean_title, extract_article


SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Great Article | Example News</title>
    <meta name="author" content="John Doe">
    <meta property="article:published_time" content="2025-01-15">
</head>
<body>
    <header>Navigation bar stuff</header>
    <article>
        <h1>Great Article</h1>
        <p>This is the main content of the article. It has enough text to be meaningful
        and should be extracted by readability. Let us add more sentences to make it long
        enough for readability to consider it the main content block. The article discusses
        various important topics that are relevant to the reader. Each paragraph adds more
        context and detail about the subject matter at hand.</p>
        <p>Another paragraph with more content to ensure readability picks this up as the
        main article body. We need sufficient text density to pass the extraction heuristics
        that readability uses internally.</p>
    </article>
    <footer>Footer stuff</footer>
</body>
</html>
"""


def test_clean_title_strips_site_name():
    assert clean_title("Article Title | Some Site") == "Article Title"
    assert clean_title("Article Title") == "Article Title"


def test_clean_title_keeps_longer_part():
    assert clean_title("Short | A Much Longer Title Here") == "A Much Longer Title Here"


def test_extract_article_returns_article_data():
    result = extract_article(SAMPLE_HTML, "https://example.com/article")

    assert isinstance(result, ArticleData)
    assert result.source_url == "https://example.com/article"


def test_extract_article_extracts_author():
    result = extract_article(SAMPLE_HTML, "https://example.com/article")
    assert result.author == "John Doe"


def test_extract_article_extracts_date():
    result = extract_article(SAMPLE_HTML, "https://example.com/article")
    assert result.date == "2025-01-15"


def test_extract_article_has_content():
    result = extract_article(SAMPLE_HTML, "https://example.com/article")
    assert len(result.content_html) > 0
    # Content should include article text
    assert "main content" in result.content_html


def test_extract_article_no_meta():
    """Handles HTML without meta tags gracefully."""
    html = "<html><head><title>Simple</title></head><body><p>Content here with enough text</p></body></html>"
    result = extract_article(html, "https://example.com")
    assert result.author == ""
    assert result.date == ""
