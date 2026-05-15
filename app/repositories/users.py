from psycopg.errors import UniqueViolation

from app.database import get_pool


class UsernameTaken(Exception):
    pass


async def create_user(username: str, password_hash: str) -> dict:
    sql = """
        INSERT INTO users (username, password_hash)
        VALUES (%s, %s)
        RETURNING id, username
    """
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            try:
                await cur.execute(sql, (username, password_hash))
            except UniqueViolation as exc:
                raise UsernameTaken(username) from exc
            row = await cur.fetchone()
    return {"id": row[0], "username": row[1]}


async def get_user_by_username(username: str) -> dict | None:
    sql = "SELECT id, username, password_hash FROM users WHERE username = %s"
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, (username,))
            row = await cur.fetchone()
    if row is None:
        return None
    return {"id": row[0], "username": row[1], "password_hash": row[2]}
