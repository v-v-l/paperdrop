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
    ["status"],
)

CONVERSION_DURATION_SECONDS = Histogram(
    "conversion_duration_seconds",
    "Total conversion time in seconds",
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

# Subscription metrics
ACTIVE_SUBSCRIPTIONS = Gauge(
    "active_subscriptions",
    "Current number of active subscriptions",
)
