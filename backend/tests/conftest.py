"""Shared test fixtures: async SQLite DB, fake Redis, test client."""

import os
import uuid
from datetime import datetime, timezone

# Set env vars BEFORE importing app modules.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["TELEGRAM_BOT_TOKEN"] = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
os.environ["TELEGRAM_WEBHOOK_URL"] = "https://example.com/webhook"
os.environ["TELEGRAM_WEBHOOK_SECRET"] = "test-secret"
os.environ["PLAYWRIGHT_ENABLED"] = "false"

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import get_session  # noqa: E402
from app.models.base import Base  # noqa: E402

# ---------------------------------------------------------------------------
# Async SQLite engine for tests
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session_factory = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@event.listens_for(test_engine.sync_engine, "connect")
def _register_sqlite_functions(dbapi_conn, connection_record):
    """Register PostgreSQL-compatible functions for SQLite."""
    dbapi_conn.create_function("gen_random_uuid", 0, lambda: str(uuid.uuid4()))


@pytest_asyncio.fixture
async def db_session():
    """Create tables, yield a session, then drop tables."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with test_session_factory() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ---------------------------------------------------------------------------
# Fake Redis
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def fake_redis():
    """Return a fakeredis async client."""
    import fakeredis.aioredis

    redis = fakeredis.aioredis.FakeRedis()
    yield redis
    await redis.flushall()
    await redis.aclose()


# ---------------------------------------------------------------------------
# FastAPI test client (with DB override, lifespan disabled)
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def test_app(db_session):
    """Create a FastAPI app instance with overridden DB session and no bot lifespan."""
    from fastapi import FastAPI

    from app.api.metrics import router as metrics_router
    from app.api.miniapp import router as miniapp_router

    app = FastAPI()
    app.include_router(metrics_router)
    app.include_router(miniapp_router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session

    yield app


@pytest_asyncio.fixture
async def client(test_app):
    """Async httpx client for testing FastAPI endpoints."""
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
