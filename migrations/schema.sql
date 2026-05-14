CREATE TABLE IF NOT EXISTS users (
    id          BIGSERIAL PRIMARY KEY,
    username    TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS authors (
    id    BIGSERIAL PRIMARY KEY,
    name  TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS books (
    id              BIGSERIAL PRIMARY KEY,
    title           TEXT   NOT NULL,
    genre           TEXT   NOT NULL,
    published_year  INT    NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS book_authors (
    book_id   BIGINT NOT NULL REFERENCES books(id)   ON DELETE CASCADE,
    author_id BIGINT NOT NULL REFERENCES authors(id) ON DELETE RESTRICT,
    PRIMARY KEY (book_id, author_id)
);

CREATE INDEX IF NOT EXISTS books_title_idx          ON books (lower(title));
CREATE INDEX IF NOT EXISTS books_genre_idx          ON books (genre);
CREATE INDEX IF NOT EXISTS books_published_year_idx ON books (published_year);
CREATE INDEX IF NOT EXISTS book_authors_author_idx  ON book_authors (author_id);