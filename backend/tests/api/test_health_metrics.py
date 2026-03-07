"""Tests for /health and /metrics endpoints."""

import pytest


async def test_health_endpoint(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


async def test_metrics_endpoint(client):
    response = await client.get("/metrics")
    assert response.status_code == 200
    # Prometheus format: content-type should be text/plain or openmetrics
    assert "text/plain" in response.headers["content-type"] or "openmetrics" in response.headers["content-type"]
    # Should contain some metric names
    body = response.text
    assert "python_info" in body or "process_" in body or "http_" in body
