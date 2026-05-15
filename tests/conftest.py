import os
import sys
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Test config — must be set BEFORE importing the app modules.
# Override DATABASE_URL in your shell to point at your local Postgres.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/books_test",
)
os.environ.setdefault("JWT_SECRET", "test-secret-please-rotate-and-make-it-long-enough-for-hs256")
os.environ.setdefault("JWT_EXPIRES_MINUTES", "60")

from app.config import get_settings  # noqa: E402
from app.database import close_pool, drop_schema, init_schema  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest_asyncio.fixture
async def _fresh_schema():
    """Reset DB schema between integration tests so each starts clean."""
    get_settings.cache_clear()
    await drop_schema()
    await init_schema()
    yield
    await close_pool()


@pytest_asyncio.fixture
async def client(_fresh_schema):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def auth_token(client: AsyncClient) -> str:
    username = f"user_{uuid.uuid4().hex[:8]}"
    password = "supersecret1"
    r = await client.post("/auth/register", json={"username": username, "password": password})
    assert r.status_code == 201, r.text
    r = await client.post(
        "/auth/login",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest_asyncio.fixture
async def auth_headers(auth_token: str) -> dict:
    return {"Authorization": f"Bearer {auth_token}"}