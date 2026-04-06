"""Tests for DB resilience: retry, Redis queue, and drain."""

import json

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db_resilience import (
    DB_ERRORS,
    PENDING_WRITES_KEY,
    drain_pending_writes,
    generate_conversion_id,
    resilient_db_write,
)
from app.models.conversion import Conversion, ConversionStatus
from app.models.user import User


@pytest.fixture
def conversion_id():
    return generate_conversion_id()


@pytest.fixture
def session_factory(db_session):
    """Wrap the test db_session in a factory-like callable."""
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _factory():
        yield db_session

    return _factory


@pytest_asyncio.fixture
async def user(db_session):
    """Create a test user."""
    u = User(id=111222333, total_conversions=0)
    db_session.add(u)
    await db_session.commit()
    return u


class TestGenerateConversionId:
    def test_returns_uuid_string(self):
        cid = generate_conversion_id()
        assert len(cid) == 36
        assert cid.count("-") == 4

    def test_unique(self):
        ids = {generate_conversion_id() for _ in range(100)}
        assert len(ids) == 100


class TestResilientDbWrite:
    @pytest.mark.asyncio
    async def test_create_conversion(self, session_factory, fake_redis, user, db_session):
        cid = generate_conversion_id()
        await resilient_db_write(
            session_factory, fake_redis,
            "create_conversion",
            {"id": cid, "user_id": user.id, "url": "https://example.com", "status": "processing"},
        )
        result = await db_session.get(Conversion, cid)
        assert result is not None
        assert result.url == "https://example.com"

    @pytest.mark.asyncio
    async def test_update_conversion(self, session_factory, fake_redis, user, db_session):
        cid = generate_conversion_id()
        conv = Conversion(id=cid, user_id=user.id, url="https://example.com", status="processing")
        db_session.add(conv)
        await db_session.commit()

        await resilient_db_write(
            session_factory, fake_redis,
            "update_conversion",
            {"id": cid, "status": "completed", "title": "Test Article"},
        )
        await db_session.refresh(conv)
        assert conv.status == "completed"
        assert conv.title == "Test Article"

    @pytest.mark.asyncio
    async def test_increment_user_conversions(self, session_factory, fake_redis, user, db_session):
        await resilient_db_write(
            session_factory, fake_redis,
            "increment_user_conversions",
            {"user_id": user.id},
        )
        await db_session.refresh(user)
        assert user.total_conversions == 1


class TestQueueAndDrain:
    @pytest.mark.asyncio
    async def test_drain_creates_conversion(self, session_factory, fake_redis, user, db_session):
        cid = generate_conversion_id()
        entry = json.dumps({
            "op": "create_conversion",
            "params": {"id": cid, "user_id": user.id, "url": "https://queued.com", "status": "completed"},
            "queued_at": "2026-04-05T12:00:00+00:00",
        })
        await fake_redis.lpush(PENDING_WRITES_KEY, entry)

        drained = await drain_pending_writes(session_factory, fake_redis)
        assert drained == 1

        result = await db_session.get(Conversion, cid)
        assert result is not None
        assert result.url == "https://queued.com"

    @pytest.mark.asyncio
    async def test_drain_empty_queue(self, session_factory, fake_redis):
        drained = await drain_pending_writes(session_factory, fake_redis)
        assert drained == 0

    @pytest.mark.asyncio
    async def test_drain_multiple_ops(self, session_factory, fake_redis, user, db_session):
        cid = generate_conversion_id()
        ops = [
            {"op": "create_conversion", "params": {"id": cid, "user_id": user.id, "url": "https://a.com", "status": "processing"}, "queued_at": "t1"},
            {"op": "update_conversion", "params": {"id": cid, "status": "completed", "title": "Done"}, "queued_at": "t2"},
            {"op": "increment_user_conversions", "params": {"user_id": user.id}, "queued_at": "t3"},
        ]
        for op in ops:
            await fake_redis.lpush(PENDING_WRITES_KEY, json.dumps(op))

        drained = await drain_pending_writes(session_factory, fake_redis)
        assert drained == 3

        conv = await db_session.get(Conversion, cid)
        assert conv.status == "completed"
        assert conv.title == "Done"

        await db_session.refresh(user)
        assert user.total_conversions == 1
