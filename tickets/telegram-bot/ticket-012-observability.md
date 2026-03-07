**title**: Prometheus /metrics endpoint for observability
**agent**: backend-developer
**depends-on**: ticket-006
**blocks**: None

## Problem
We need a `/metrics` endpoint that Prometheus can scrape for monitoring. Prometheus and Grafana are external -- we only expose the metrics.

## Requirements
- [x] Create `backend/app/core/metrics.py` with prometheus_client metrics:
  - `http_requests_total` (Counter) -- labels: method, endpoint, status
  - `http_request_duration_seconds` (Histogram) -- labels: method, endpoint
  - `conversions_total` (Counter) -- labels: status (completed, failed)
  - `conversion_duration_seconds` (Histogram) -- total conversion time
  - `active_conversions` (Gauge) -- currently processing conversions
  - `telegram_updates_total` (Counter) -- labels: update_type (message, command, payment)
  - `active_subscriptions` (Gauge) -- current active subscription count
- [x] Create `/metrics` endpoint in `backend/app/api/metrics.py`:
  - Returns `prometheus_client.generate_latest()` with correct content type
  - No authentication (Prometheus scrapes this)
- [x] Add middleware to track HTTP request metrics (count + latency)
- [x] Instrument conversion task with timing and status counters
- [x] Instrument Telegram update processing with counters

## Scope
- `backend/app/core/metrics.py` -- metric definitions
- `backend/app/api/metrics.py` -- /metrics endpoint
- `backend/app/main.py` -- add metrics middleware, register metrics route

## Notes
- Use `prometheus_client` library (already in dependencies from ticket-001)
- The middleware should exclude `/metrics` and `/health` from tracking to avoid noise
- `active_subscriptions` gauge can be updated periodically or on subscription change events
- Conversion metrics should be updated in the ARQ task (ticket-005), not in the HTTP layer
- No docker-compose for Prometheus/Grafana -- they are external services
