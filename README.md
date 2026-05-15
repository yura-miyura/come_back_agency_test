# Books API

A FastAPI + PostgreSQL service for managing a catalog of books, with JWT
authentication, bulk import (JSON/CSV), filtering, pagination, and sorting.

## Stack

- **FastAPI** for the HTTP layer
- **PostgreSQL** with **raw SQL** via async `psycopg` 3 (no ORM)
- **PyJWT** + **bcrypt** for auth
- **pytest** for unit + integration tests

## Design notes

- **Normalized schema**: `books`, `authors`, and a `book_authors` join table.
  Books are many-to-many with authors so a single author appearing on multiple
  books is stored once.
- **Raw SQL** — every database call uses parameterised SQL through psycopg,
  not an ORM (matches the spec).
- **Validation lives in Pydantic** (`schemas.py`): non-empty title/authors,
  `published_year` ∈ [1800, current year], genre against an allow-list
  (configurable in `config.py`).
- **Auth**: bcrypt-hashed passwords, JWT bearer tokens via OAuth2 password flow.
  Create / update / delete / import endpoints require a valid token; reads
  are public.

## Project layout

```
app/                        application package
  __init__.py
  main.py                   FastAPI app + lifespan + error handler
  config.py                 settings (env-driven)
  database.py               async psycopg pool + schema bootstrap
  auth.py                   password hashing, JWT, current-user dependency
  schemas.py                Pydantic request/response models with validators
  repositories/
    users.py                raw SQL for users
    books.py                raw SQL for books + author upserts
  routers/
    auth.py                 /auth/register, /auth/login
    books.py                /books CRUD + bulk import
migrations/schema.sql       DDL — applied on app startup
sample_data/books.csv       sample file you can feed to /books/import
tests/                      pytest unit + integration tests
  conftest.py
  test_unit_*.py            DB-free unit tests
  test_api_*.py             end-to-end API tests (require Postgres)
pyproject.toml              dependencies + pytest config
.env.example                template for local env vars
.gitignore
README.md
```

## Running locally

1. Install Python ≥3.11 and PostgreSQL.
2. Create a database, e.g. `createdb books`.
3. Copy `.env.example` to `.env` and edit:

   ```
   DATABASE_URL=postgresql://<user>:<pass>@localhost:5432/books
   JWT_SECRET=<a long random string, at least 32 bytes>
   ```

4. Install deps (using `uv`):

   ```bash
   uv sync --extra dev
   ```

   Or with pip:

   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -e '.[dev]'
   ```

5. Run the server (schema is created on startup):

   ```bash
   uvicorn app.main:app --reload
   ```

   The interactive docs are at <http://localhost:8000/docs>.

## Running tests

The test suite hits a real PostgreSQL instance — it does not mock the DB,
since the spec requires raw SQL.

1. Create an empty test database, e.g. `createdb books_test`.
2. Run:

   ```bash
   DATABASE_URL="postgresql://<user>@localhost:5432/books_test" \
     pytest
   ```

Unit tests in `tests/test_unit_*` don't need the database and will run even
without `DATABASE_URL` pointing at a live server (the autouse DB fixture is
scoped to the integration `client` fixture).

## API summary

| Method | Path                  | Auth | Description |
| ------ | --------------------- | ---- | ----------- |
| POST   | `/auth/register`      | —    | Create user (`username`, `password`) |
| POST   | `/auth/login`         | —    | OAuth2 password flow; returns JWT |
| GET    | `/books`              | —    | List w/ filters + pagination + sorting |
| POST   | `/books`              | yes  | Create a book |
| GET    | `/books/{id}`         | —    | Get one |
| PATCH  | `/books/{id}`         | yes  | Partial update |
| DELETE | `/books/{id}`         | yes  | Delete |
| POST   | `/books/import`       | yes  | Bulk import a JSON or CSV file |
| GET    | `/health`             | —    | Liveness probe |

### List query parameters

- `title` — case-insensitive substring match
- `author` — case-insensitive substring match against any of the book's authors
- `genre` — exact match (must be in the allow-list)
- `year_from`, `year_to` — inclusive range over `published_year`
- `sort_by` — `id` (default), `title`, `published_year`, `created_at`, `author`
- `sort_dir` — `asc` (default), `desc`
- `limit` — 1..200, default 20
- `offset` — ≥0, default 0

### Bulk import

`POST /books/import` accepts `multipart/form-data` with a single `file` field.

- **JSON** files: an array of objects, each shaped like a `POST /books` body.
- **CSV** files with header row `title,authors,genre,published_year`.
  Multiple authors per book go in the `authors` column separated by `;`.

The response lists how many rows were inserted and per-row validation errors
so a partial-success import is reported transparently.

A sample CSV is included at `sample_data/books.csv`. Quick try-it-out:

```bash
# get a token first (replace credentials)
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -d 'username=user1&password=supersecret1' | jq -r .access_token)

curl -X POST http://localhost:8000/books/import \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@sample_data/books.csv"
```

## Security notes

- The original `database.py` checked in to this repo contained a real Neon
  Postgres connection string with credentials. I replaced it with an
  env-var-driven config; **please rotate the password on that Neon database**.
- Pick a long random `JWT_SECRET` (≥32 bytes). The default in `config.py` is
  intentionally insecure and exists only so the app can boot.