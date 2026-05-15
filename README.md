# Books API

A FastAPI + PostgreSQL service for managing a catalogue of books. Supports
JWT-authenticated CRUD, filtering / pagination / sorting on the list
endpoint, and bulk import from JSON or CSV files. Database access is via
raw SQL (psycopg 3, async). Authors are normalised into their own table
with a many-to-many join to books.

## Requirements

- Python 3.11+
- PostgreSQL 13+ running locally (or accessible via `DATABASE_URL`)

## Quick start

```bash
# 1. create the application database
createdb books

# 2. install dependencies — pick one of:

# with uv
uv sync --extra dev

# OR with pip
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# 3. configure (or copy .env.example to .env and edit)
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/books"
export JWT_SECRET="a-long-random-string-at-least-32-bytes"

# 4. run the server (schema is created automatically on startup)
uvicorn app.main:app --reload
```

If you only want runtime deps (no test tools), install
`requirements.txt` instead of `requirements-dev.txt`.

## API documentation

The server exposes auto-generated, fully-interactive API docs:

- **Swagger UI**: <http://localhost:8000/docs> — try every endpoint
  from the browser, including auth (click *Authorize* at the top right
  and paste a bearer token after `/auth/login`).
- **ReDoc**: <http://localhost:8000/redoc> — read-only reference view.
- **Raw OpenAPI schema** (JSON): <http://localhost:8000/openapi.json>

The docs reflect the live Pydantic schemas, so request/response models,
validation rules (year range, genre allow-list, etc.), and example
payloads are always up to date with the code.

## Database migrations

The schema lives in [`migrations/schema.sql`](migrations/schema.sql) —
a single idempotent file with the `users`, `authors`, `books`, and
`book_authors` tables plus supporting indexes (`CREATE TABLE IF NOT
EXISTS`, `CREATE INDEX IF NOT EXISTS`).

It is applied automatically on application startup via
`app.database.init_schema()` in the FastAPI lifespan hook, so a fresh
database becomes ready as soon as `uvicorn app.main:app` starts.

To apply it manually (CI, container build, etc.):

```bash
psql "$DATABASE_URL" -f migrations/schema.sql
```

Schema changes for now go directly into `schema.sql`. If/when the
project grows, swap this for versioned migrations (Alembic / yoyo /
dbmate) — the current setup is intentionally minimal.

## Running tests

```bash
# create a separate test database
createdb books_test

# run the suite
DATABASE_URL="postgresql://postgres:postgres@localhost:5432/books_test" pytest
```

Unit tests in `tests/test_unit_*.py` run without a database; only the
integration tests in `tests/test_api_*.py` need Postgres.

## API summary

| Method | Path             | Auth | Description |
| ------ | ---------------- | ---- | ----------- |
| POST   | `/auth/register` | —    | Register a user |
| POST   | `/auth/login`    | —    | OAuth2 password flow; returns a JWT |
| GET    | `/books/`        | —    | List with filters + pagination + sorting |
| POST   | `/books/`        | yes  | Create a book |
| GET    | `/books/{id}`    | —    | Get one |
| PATCH  | `/books/{id}`    | yes  | Partial update |
| DELETE | `/books/{id}`    | yes  | Delete |
| POST   | `/books/import`  | yes  | Bulk import a JSON or CSV file |
| GET    | `/health`        | —    | Liveness probe |

List supports the query parameters `title`, `author`, `genre`,
`year_from`, `year_to`, `sort_by` (`id` / `title` / `published_year` /
`created_at` / `author`), `sort_dir` (`asc` / `desc`), `limit` (1..200,
default 20), and `offset` (default 0).

### Sample bulk import

A ready-to-use CSV is included at `sample_data/books.csv`:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -d 'username=user1&password=supersecret1' | jq -r .access_token)

curl -X POST http://localhost:8000/books/import \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@sample_data/books.csv"
```

CSV format: header row `title,authors,genre,published_year`; multiple
authors inside a single cell are separated by `;`. JSON format: an
array of objects shaped like a `POST /books/` body.

## Project layout

```
app/
  main.py            FastAPI app + lifespan + error handler
  config.py          env-driven settings
  database.py        async psycopg pool + schema bootstrap
  auth.py            bcrypt + JWT + get_current_user dependency
  schemas.py         Pydantic request / response models
  repositories/      raw-SQL data access (books, users)
  routers/           HTTP endpoints (auth, books)
migrations/schema.sql   DDL applied on startup
sample_data/books.csv   sample for the /books/import endpoint
tests/                  pytest unit + integration tests
pyproject.toml          uv / hatch project metadata
requirements*.txt       pip-compatible dep lists
```

## Security note

The original `database.py` was checked in with real Neon Postgres
credentials. They've been removed from the working tree but remain in
git history — **please rotate that password**. Also generate a strong
`JWT_SECRET`; the fallback in `config.py` is insecure on purpose so the
app can boot during development.
