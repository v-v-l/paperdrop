"""Prometheus metrics definitions.

All metrics that depend on worker state are refreshed from the database on
each /metrics scrape, because the worker runs in a separate container and
cannot share in-process counters.
"""

from datetime import datetime, timezone

from prometheus_client import Counter, Gauge, Histogram
from sqlalchemy import case, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

# HTTP metrics (backend process — works in-process)
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

# Telegram metrics (backend process — works in-process)
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

# Rate limiting & funnel metrics (backend process — works in-process)
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
# These cover worker-written data that can't be tracked in-process.

CONVERSIONS_TOTAL = Gauge(
    "conversions_total",
    "Total conversions by status and source type",
    ["status", "source_type"],
)

ACTIVE_CONVERSIONS = Gauge(
    "active_conversions",
    "Number of conversions currently being processed",
)

CONVERSION_DURATION_AVG_SECONDS = Gauge(
    "conversion_duration_avg_seconds",
    "Average conversion duration in seconds",
    ["source_type"],
)

KINDLE_DELIVERIES_TOTAL = Gauge(
    "kindle_deliveries_total",
    "Total Kindle delivery attempts",
    ["status"],
)

ACTIVE_SUBSCRIPTIONS = Gauge(
    "active_subscriptions",
    "Current number of active subscriptions",
)

TOTAL_USERS = Gauge(
    "total_users",
    "Total registered users",
)

# Bot health
BOT_WEBHOOK_HEALTHY = Gauge(
    "bot_webhook_healthy",
    "Whether the bot webhook is set up and functional (1=healthy, 0=unhealthy)",
)


def _source_type_expr(url_column):
    """SQL expression to derive source_type from the URL column."""
    return case(
        (url_column.like("file://%.pdf"), "pdf"),
        (url_column.like("file://%"), "epub"),
        else_="url",
    )


async def refresh_db_metrics(session: AsyncSession) -> None:
    """Query the database and update gauges that depend on worker-written data.

    Called from the /metrics endpoint before generating output.
    """
    from app.models.conversion import Conversion
    from app.models.subscription import Subscription, SubscriptionStatus
    from app.models.user import User

    # --- Conversions by status and source_type ---
    source_type = _source_type_expr(Conversion.url)
    result = await session.execute(
        select(Conversion.status, source_type, func.count())
        .group_by(Conversion.status, source_type)
    )
    # Reset all known label combinations to 0
    for status in ("completed", "failed", "pending", "processing"):
        for st in ("url", "epub", "pdf"):
            CONVERSIONS_TOTAL.labels(status=status, source_type=st).set(0)
    for status, stype, count in result.all():
        CONVERSIONS_TOTAL.labels(status=status, source_type=stype).set(count)

    # --- Active conversions (currently processing) ---
    result = await session.execute(
        select(func.count()).select_from(Conversion)
        .where(Conversion.status == "processing")
    )
    ACTIVE_CONVERSIONS.set(result.scalar_one())

    # --- Average conversion duration by source_type ---
    result = await session.execute(
        select(
            source_type,
            func.avg(
                extract("epoch", Conversion.completed_at) -
                extract("epoch", Conversion.created_at)
            ),
        )
        .where(Conversion.completed_at.is_not(None))
        .group_by(source_type)
    )
    for st in ("url", "epub", "pdf"):
        CONVERSION_DURATION_AVG_SECONDS.labels(source_type=st).set(0)
    for stype, avg_dur in result.all():
        if avg_dur is not None:
            CONVERSION_DURATION_AVG_SECONDS.labels(source_type=stype).set(avg_dur)

    # --- Active subscriptions ---
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(func.count()).select_from(Subscription).where(
            Subscription.status == SubscriptionStatus.ACTIVE.value,
            Subscription.current_period_end >= now,
        )
    )
    ACTIVE_SUBSCRIPTIONS.set(result.scalar_one())

    # --- Kindle deliveries by status ---
    result = await session.execute(
        select(Conversion.kindle_status, func.count())
        .where(Conversion.kindle_status.is_not(None))
        .group_by(Conversion.kindle_status)
    )
    KINDLE_DELIVERIES_TOTAL.labels(status="success").set(0)
    KINDLE_DELIVERIES_TOTAL.labels(status="failed").set(0)
    for status, count in result.all():
        KINDLE_DELIVERIES_TOTAL.labels(status=status).set(count)

    # --- Total users ---
    result = await session.execute(
        select(func.count()).select_from(User)
    )
    TOTAL_USERS.set(result.scalar_one())
