"""Shared pytest fixtures: an httpx AsyncClient wired to the FastAPI app. The app is
fully stateless (no DB, no accounts), so no fixture setup/teardown is needed beyond that."""
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    from app.core.rate_limit import limiter
    from app.main import app

    limiter.reset()  # the limiter's in-memory storage is a process-wide singleton;
    # without resetting, rate limits accumulate across tests in the same run.

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
