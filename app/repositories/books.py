from psycopg import AsyncConnection
from psycopg.rows import dict_row

from app.database import get_pool

SORTABLE_FIELDS = {"title", "published_year", "created_at", "id"}
# Author sort needs join — handled separately.


async def _upsert_authors(conn: AsyncConnection, names: list[str]) -> list[int]:
    """Insert any new authors, return ids in the same order as `names`."""
    if not names:
        return []
    ids: list[int] = []
    async with conn.cursor() as cur:
        for name in names:
            await cur.execute(
                """
                INSERT INTO authors (name)
                VALUES (%s)
                ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                RETURNING id
                """,
                (name,),
            )
            row = await cur.fetchone()
            ids.append(row[0])
    return ids


async def _attach_authors(conn: AsyncConnection, book_id: int, author_ids: list[int]) -> None:
    async with conn.cursor() as cur:
        for aid in author_ids:
            await cur.execute(
                """
                INSERT INTO book_authors (book_id, author_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """,
                (book_id, aid),
            )


async def _fetch_book(conn: AsyncConnection, book_id: int) -> dict | None:
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            SELECT b.id,
                   b.title,
                   b.genre,
                   b.published_year,
                   b.created_at,
                   COALESCE(
                     ARRAY_AGG(a.name ORDER BY a.name) FILTER (WHERE a.id IS NOT NULL),
                     ARRAY[]::text[]
                   ) AS authors
            FROM books b
            LEFT JOIN book_authors ba ON ba.book_id = b.id
            LEFT JOIN authors a       ON a.id = ba.author_id
            WHERE b.id = %s
            GROUP BY b.id
            """,
            (book_id,),
        )
        return await cur.fetchone()


async def create_book(
    *, title: str, authors: list[str], genre: str, published_year: int
) -> dict:
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.transaction():
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO books (title, genre, published_year)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (title, genre, published_year),
                )
                book_id = (await cur.fetchone())[0]
            author_ids = await _upsert_authors(conn, authors)
            await _attach_authors(conn, book_id, author_ids)
        return await _fetch_book(conn, book_id)


async def get_book(book_id: int) -> dict | None:
    pool = get_pool()
    async with pool.connection() as conn:
        return await _fetch_book(conn, book_id)


async def update_book(
    book_id: int,
    *,
    title: str | None = None,
    authors: list[str] | None = None,
    genre: str | None = None,
    published_year: int | None = None,
) -> dict | None:
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.transaction():
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1 FROM books WHERE id = %s", (book_id,))
                if await cur.fetchone() is None:
                    return None

            sets: list[str] = []
            params: list = []
            if title is not None:
                sets.append("title = %s")
                params.append(title)
            if genre is not None:
                sets.append("genre = %s")
                params.append(genre)
            if published_year is not None:
                sets.append("published_year = %s")
                params.append(published_year)
            if sets:
                params.append(book_id)
                async with conn.cursor() as cur:
                    await cur.execute(
                        f"UPDATE books SET {', '.join(sets)} WHERE id = %s",
                        params,
                    )
            if authors is not None:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "DELETE FROM book_authors WHERE book_id = %s", (book_id,)
                    )
                author_ids = await _upsert_authors(conn, authors)
                await _attach_authors(conn, book_id, author_ids)
        return await _fetch_book(conn, book_id)


async def delete_book(book_id: int) -> bool:
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM books WHERE id = %s", (book_id,))
            return cur.rowcount > 0


async def list_books(
    *,
    title: str | None = None,
    author: str | None = None,
    genre: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    sort_by: str = "id",
    sort_dir: str = "asc",
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int]:
    if sort_by not in SORTABLE_FIELDS and sort_by != "author":
        raise ValueError(f"sort_by must be one of {SORTABLE_FIELDS | {'author'}}")
    if sort_dir.lower() not in {"asc", "desc"}:
        raise ValueError("sort_dir must be 'asc' or 'desc'")
    sort_dir_sql = sort_dir.upper()

    where: list[str] = []
    params: list = []
    if title is not None:
        where.append("b.title ILIKE %s")
        params.append(f"%{title}%")
    if genre is not None:
        where.append("b.genre = %s")
        params.append(genre)
    if year_from is not None:
        where.append("b.published_year >= %s")
        params.append(year_from)
    if year_to is not None:
        where.append("b.published_year <= %s")
        params.append(year_to)

    author_join = ""
    if author is not None:
        author_join = "JOIN book_authors ba2 ON ba2.book_id = b.id JOIN authors a2 ON a2.id = ba2.author_id"
        where.append("a2.name ILIKE %s")
        params.append(f"%{author}%")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    if sort_by == "author":
        order_sql = (
            "ORDER BY (SELECT MIN(a3.name) FROM book_authors ba3 "
            "JOIN authors a3 ON a3.id = ba3.author_id WHERE ba3.book_id = b.id) "
            f"{sort_dir_sql} NULLS LAST, b.id ASC"
        )
    else:
        order_sql = f"ORDER BY b.{sort_by} {sort_dir_sql}, b.id ASC"

    list_sql = f"""
        SELECT b.id, b.title, b.genre, b.published_year, b.created_at,
               COALESCE(
                 ARRAY_AGG(a.name ORDER BY a.name) FILTER (WHERE a.id IS NOT NULL),
                 ARRAY[]::text[]
               ) AS authors
        FROM books b
        LEFT JOIN book_authors ba ON ba.book_id = b.id
        LEFT JOIN authors a       ON a.id = ba.author_id
        {author_join}
        {where_sql}
        GROUP BY b.id
        {order_sql}
        LIMIT %s OFFSET %s
    """
    count_sql = f"""
        SELECT COUNT(DISTINCT b.id) FROM books b
        {author_join}
        {where_sql}
    """

    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(count_sql, params)
            total = (await cur.fetchone())[0]
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(list_sql, [*params, limit, offset])
            rows = await cur.fetchall()
    return rows, total