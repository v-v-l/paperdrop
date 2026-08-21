"""Regression tests for webhook setup recovery after a late dependency.

Docker ignores depends_on on unattended restarts, so the local Bot API server
can come up after the bounded startup retries have already been exhausted.
"""

import asyncio

import pytest

from app.core.metrics import BOT_WEBHOOK_HEALTHY
from app.main import _recover_webhook_forever, _setup_webhook_with_retry


_real_sleep = asyncio.sleep


@pytest.fixture(autouse=True)
def _fast_retries(monkeypatch):
    """Collapse the backoff so the tests do not actually sleep."""

    async def _no_sleep(_delay):
        await _real_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", _no_sleep)


async def test_setup_reports_failure_and_zeroes_gauge(monkeypatch):
    BOT_WEBHOOK_HEALTHY.set(1)
    monkeypatch.setattr(
        "app.main.setup_webhook",
        _raiser(ConnectionError("bot api not up")),
    )

    assert await _setup_webhook_with_retry(object()) is False
    assert BOT_WEBHOOK_HEALTHY._value.get() == 0


async def test_setup_reports_success(monkeypatch):
    BOT_WEBHOOK_HEALTHY.set(0)
    monkeypatch.setattr("app.main.setup_webhook", _succeeder())

    assert await _setup_webhook_with_retry(object()) is True
    assert BOT_WEBHOOK_HEALTHY._value.get() == 1


async def test_recovery_flips_gauge_once_dependency_returns(monkeypatch):
    """The incident: dependency arrives after startup retries are exhausted."""
    BOT_WEBHOOK_HEALTHY.set(0)
    calls = {"n": 0}

    async def flaky(_application):
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("bot api not up")

    monkeypatch.setattr("app.main.setup_webhook", flaky)

    await asyncio.wait_for(_recover_webhook_forever(object()), timeout=5)

    assert calls["n"] == 3
    assert BOT_WEBHOOK_HEALTHY._value.get() == 1


def _raiser(exc):
    async def _fn(_application):
        raise exc

    return _fn


def _succeeder():
    async def _fn(_application):
        return None

    return _fn
