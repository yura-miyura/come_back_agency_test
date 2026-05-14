from pathlib import Path

from psycopg_pool import AsyncConnectionPool

from app.config import get_settings

_pool: AsyncConnectionPool | None = None
SCHEMA_PATH = Path(__file__).resolve().parent.parent / "migrations" / "schema.sql"


async def open_pool() -> AsyncConnectionPool:
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = AsyncConnectionPool(
            settings.database_url, open=False, min_size=1, max_size=10
        )
        await _pool.open()
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> AsyncConnectionPool:
    if _pool is None:
        raise RuntimeError("Database pool is not initialised; call open_pool() first")
    return _pool


async def init_schema() -> None:
    pool = await open_pool()
    sql = SCHEMA_PATH.read_text()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql)


async def drop_schema() -> None:
    """Test helper: wipe schema between test runs."""
    pool = await open_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DROP TABLE IF EXISTS book_authors, books, authors, users CASCADE"
            )