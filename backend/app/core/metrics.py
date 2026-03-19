"""Prometheus metrics definitions.

Metrics that depend on worker state (kindle deliveries, active subscriptions)
are refreshed from the database on each /metrics scrape, because the worker
runs in a separate container and cannot share in-process counters.
"""

from datetime import datetime, timezone

from prometheus_client import Counter, Gauge, Histogram
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

# HTTP metrics
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
)

# Conversion metrics
CONVERSIONS_TOTAL = Counter(
    "conversions_total",
    "Total conversions processed",
    ["status", "source_type"],
)

CONVERSION_DURATION_SECONDS = Histogram(
    "conversion_duration_seconds",
    "Total conversion time in seconds",
    ["source_type"],
)

ACTIVE_CONVERSIONS = Gauge(
    "active_conversions",
    "Number of conversions currently being processed",
)

# Telegram metrics
TELEGRAM_UPDATES_TOTAL = Counter(
    "telegram_updates_total",
    "Total Telegram updates received",
    ["update_type"],
)

BOT_COMMANDS_TOTAL = Counter(
    "bot_commands_total",
    "Total bot commands by command name",
    ["command"],
)

BOT_NEW_USERS_TOTAL = Counter(
    "bot_new_users_total",
    "Total new users registered via /start",
)

# Rate limiting & funnel metrics
RATE_LIMIT_HITS_TOTAL = Counter(
    "rate_limit_hits_total",
    "Total rate limit rejections",
    ["tier"],
)

FREE_TIER_LIMIT_HITS_TOTAL = Counter(
    "free_tier_limit_hits_total",
    "Total free tier limit rejections (upgrade signal)",
)

# --- DB-backed metrics (refreshed on each /metrics scrape) ---

KINDLE_DELIVERIES_TOTAL = Gauge(
    "kindle_deliveries_total",
    "Total Kindle delivery attempts",
    ["status"],
)

ACTIVE_SUBSCRIPTIONS = Gauge(
    "active_subscriptions",
    "Current number of active subscriptions",
)

# Bot health
BOT_WEBHOOK_HEALTHY = Gauge(
    "bot_webhook_healthy",
    "Whether the bot webhook is set up and functional (1=healthy, 0=unhealthy)",
)


async def refresh_db_metrics(session: AsyncSession) -> None:
    """Query the database and update gauges that depend on worker-written data.

    Called from the /metrics endpoint before generating output.
    """
    from app.models.conversion import Conversion
    from app.models.subscription import Subscription, SubscriptionStatus

    # Active subscriptions: status=active AND not expired
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(func.count()).select_from(Subscription).where(
            Subscription.status == SubscriptionStatus.ACTIVE.value,
            Subscription.current_period_end >= now,
        )
    )
    ACTIVE_SUBSCRIPTIONS.set(result.scalar_one())

    # Kindle deliveries by status (from conversion records)
    result = await session.execute(
        select(Conversion.kindle_status, func.count())
        .where(Conversion.kindle_status.is_not(None))
        .group_by(Conversion.kindle_status)
    )
    # Reset to 0 first (so disappeared statuses don't show stale values)
    KINDLE_DELIVERIES_TOTAL.labels(status="success").set(0)
    KINDLE_DELIVERIES_TOTAL.labels(status="failed").set(0)
    for status, count in result.all():
        KINDLE_DELIVERIES_TOTAL.labels(status=status).set(count)
