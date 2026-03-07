FROM python:3.12-slim

# System deps for lxml, Pillow, Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    libffi-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev --no-install-project

# Install Playwright Chromium
RUN uv run playwright install --with-deps chromium

# Copy application code
COPY app/ app/
COPY migrations/ migrations/
COPY alembic.ini .
COPY miniapp/ miniapp/

# Create temp directory
RUN mkdir -p /tmp/links_to_epub

EXPOSE 8040

# Default: run the API server
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8040"]
