import hashlib
import secrets
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.db.session import Base, get_db
from src.main import app
from src.models.incidents import Tenant

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    Session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with Session() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def tenant(db_session) -> tuple[Tenant, str]:
    """Returns (tenant, raw_api_key)."""
    raw_key = secrets.token_hex(32)
    t = Tenant(
        name="Test Tenant",
        slack_webhook_url="https://hooks.slack.com/test",
        api_key_hash=hashlib.sha256(raw_key.encode()).hexdigest(),
    )
    db_session.add(t)
    await db_session.commit()
    await db_session.refresh(t)
    return t, raw_key
