"""Prometheus metrics definitions."""

from prometheus_client import Counter, Gauge, Histogram

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

# Kindle delivery metrics
KINDLE_DELIVERIES_TOTAL = Counter(
    "kindle_deliveries_total",
    "Total Kindle delivery attempts",
    ["status"],
)

# Subscription metrics
ACTIVE_SUBSCRIPTIONS = Gauge(
    "active_subscriptions",
    "Current number of active subscriptions",
)

# Bot health
BOT_WEBHOOK_HEALTHY = Gauge(
    "bot_webhook_healthy",
    "Whether the bot webhook is set up and functional (1=healthy, 0=unhealthy)",
)
