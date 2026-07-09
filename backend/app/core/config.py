from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Look for .env in project root (one level above backend/)
_env_file = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_env_file),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/links_to_epub"

    # Redis (ARQ task queue)
    REDIS_URL: str = "redis://localhost:6379/0"

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_WEBHOOK_URL: str = ""
    TELEGRAM_WEBHOOK_SECRET: str = ""
    TELEGRAM_PAYMENT_PROVIDER_TOKEN: str = ""
    TELEGRAM_API_BASE_URL: str = "https://api.telegram.org/bot"
    TELEGRAM_API_BASE_FILE_URL: str = "https://api.telegram.org/file/bot"
    TELEGRAM_LOCAL_MODE: bool = False
    TELEGRAM_MAX_FILE_SIZE: int = 104857600  # 100 MB

    # Subscription
    SUBSCRIPTION_PRICE_STARS: int = 250  # Telegram Stars (~$4.99)
    FREE_TIER_LIMIT: int = 5

    # Rate limiting (per-user, sliding window)
    RATE_LIMIT_FREE_MAX: int = 3
    RATE_LIMIT_FREE_WINDOW: int = 3600  # seconds (1 hour)
    RATE_LIMIT_PAID_MAX: int = 20
    RATE_LIMIT_PAID_WINDOW: int = 3600  # seconds (1 hour)

    # Email (Resend — Send-to-Kindle)
    RESEND_API_KEY: str = ""
    SENDER_EMAIL: str = "send@paperdrop.bp-flow.com"

    # File processing APIs
    EPUB_FIXER_URL: str = "http://192.168.100.70:8010/convert"
    EPUB_API_KEY: str = ""
    PDF_TO_EPUB_URL: str = "http://host.docker.internal:8100/api/convert"
    # Below this ratio of pages-with-text, treat a PDF as scanned/image-only and
    # deliver the original PDF instead of a mostly-empty reflowed EPUB.
    PDF_MIN_TEXT_COVERAGE: float = 0.40

    # Playwright
    PLAYWRIGHT_ENABLED: bool = True

    # Mini App
    MINI_APP_URL: str = "https://localhost:3100"

    # Application
    APP_PORT: int = 8040
    BASE_URL: str = "http://localhost:8040"
    TEMP_DIR: str = "/tmp/links_to_epub"
    LOG_LEVEL: str = "INFO"


settings = Settings()
