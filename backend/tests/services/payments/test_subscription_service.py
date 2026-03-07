"""Tests for subscription service: create, check, can_convert."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.models.subscription import Subscription, SubscriptionStatus
from app.models.user import User
from app.services.payments.subscription_service import (
    SUBSCRIPTION_PERIOD_DAYS,
    can_convert,
    check_subscription,
)


@pytest.fixture
async def user_in_db(db_session):
    """Create a test user in the DB."""
    user = User(
        id=111,
        username="testuser",
        first_name="Test",
        total_conversions=0,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _create_subscription(
    db_session,
    user_id: int,
    *,
    status: str = SubscriptionStatus.ACTIVE.value,
    days_offset: int = 0,
    period_days: int = SUBSCRIPTION_PERIOD_DAYS,
) -> Subscription:
    """Helper to create a subscription directly (SQLite-compatible, naive datetimes)."""
    # SQLite strips timezone info, so use naive UTC datetimes
    now = datetime.utcnow() + timedelta(days=days_offset)
    sub = Subscription(
        id=str(uuid.uuid4()),
        user_id=user_id,
        telegram_payment_charge_id="tg_charge",
        provider_payment_charge_id="stripe_charge",
        status=status,
        current_period_start=now,
        current_period_end=now + timedelta(days=period_days),
    )
    db_session.add(sub)
    await db_session.commit()
    await db_session.refresh(sub)
    return sub


def _utcnow_naive():
    """Return a naive UTC datetime matching what SQLite returns."""
    return datetime.utcnow()


async def test_create_active_subscription(db_session, user_in_db):
    """An active subscription can be created and queried."""
    sub = await _create_subscription(db_session, user_in_db.id)

    assert sub.user_id == user_in_db.id
    assert sub.status == SubscriptionStatus.ACTIVE.value
    assert sub.current_period_end > _utcnow_naive()


async def test_check_subscription_active(db_session, user_in_db):
    """Active subscription returns True."""
    await _create_subscription(db_session, user_in_db.id)
    # Patch datetime.now in the service to return naive UTC (matching SQLite)
    fake_now = _utcnow_naive()
    with patch(
        "app.services.payments.subscription_service.datetime"
    ) as mock_dt:
        mock_dt.now.return_value = fake_now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = await check_subscription(db_session, user_in_db.id)
    assert result is True


async def test_check_subscription_none(db_session, user_in_db):
    """No subscription returns False."""
    assert await check_subscription(db_session, user_in_db.id) is False


async def test_check_subscription_cancelled(db_session, user_in_db):
    """Cancelled subscription returns False."""
    await _create_subscription(
        db_session, user_in_db.id, status=SubscriptionStatus.CANCELLED.value
    )
    assert await check_subscription(db_session, user_in_db.id) is False


async def test_check_subscription_expired_auto_marks(db_session, user_in_db):
    """Expired subscription is auto-marked and returns False."""
    sub = await _create_subscription(
        db_session, user_in_db.id, days_offset=-31, period_days=0
    )
    # Period end is 31 days ago -- expired
    # Patch datetime.now to return naive UTC
    fake_now = _utcnow_naive()
    with patch(
        "app.services.payments.subscription_service.datetime"
    ) as mock_dt:
        mock_dt.now.return_value = fake_now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = await check_subscription(db_session, user_in_db.id)
    assert result is False

    await db_session.refresh(sub)
    assert sub.status == SubscriptionStatus.EXPIRED.value


async def test_can_convert_with_active_subscription(db_session, user_in_db):
    await _create_subscription(db_session, user_in_db.id)
    fake_now = _utcnow_naive()
    with patch(
        "app.services.payments.subscription_service.datetime"
    ) as mock_dt:
        mock_dt.now.return_value = fake_now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        allowed, reason = await can_convert(db_session, user_in_db.id)
    assert allowed is True
    assert reason == ""


async def test_can_convert_free_tier_under_limit(db_session, user_in_db):
    """User with no subscription but under free limit can convert."""
    allowed, reason = await can_convert(db_session, user_in_db.id)
    assert allowed is True


async def test_can_convert_free_tier_limit_reached(db_session, user_in_db):
    """User at the free tier limit is blocked."""
    user_in_db.total_conversions = 5
    await db_session.commit()

    allowed, reason = await can_convert(db_session, user_in_db.id)
    assert allowed is False
    assert "limit" in reason.lower()


async def test_can_convert_user_not_found(db_session):
    """Non-existent user is denied."""
    allowed, reason = await can_convert(db_session, 99999)
    assert allowed is False
    assert "not found" in reason.lower()
