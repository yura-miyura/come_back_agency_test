from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.config import get_settings

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Username = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=64)]
Password = Annotated[str, StringConstraints(min_length=8, max_length=128)]


def _current_year() -> int:
    return datetime.now(timezone.utc).year


def _validate_year(year: int) -> int:
    if year < 1800 or year > _current_year():
        raise ValueError(f"published_year must be between 1800 and {_current_year()}")
    return year


def _validate_genre(genre: str) -> str:
    allowed = get_settings().allowed_genres
    if genre not in allowed:
        raise ValueError(f"genre must be one of: {', '.join(allowed)}")
    return genre


def _validate_authors(authors: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in authors:
        if not isinstance(raw, str):
            raise ValueError("author entries must be strings")
        name = raw.strip()
        if not name:
            raise ValueError("author name must be a non-empty string")
        if len(name) > 200:
            raise ValueError("author name too long (max 200 chars)")
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(name)
    if not cleaned:
        raise ValueError("at least one author is required")
    return cleaned


class BookBase(BaseModel):
    title: NonEmptyStr
    authors: list[str] = Field(min_length=1)
    genre: NonEmptyStr
    published_year: int

    _v_authors = field_validator("authors")(lambda cls, v: _validate_authors(v))
    _v_year    = field_validator("published_year")(lambda cls, v: _validate_year(v))
    _v_genre   = field_validator("genre")(lambda cls, v: _validate_genre(v))


class BookCreate(BookBase):
    pass


class BookUpdate(BaseModel):
    title: NonEmptyStr | None = None
    authors: list[str] | None = None
    genre: NonEmptyStr | None = None
    published_year: int | None = None

    _v_authors = field_validator("authors")(lambda cls, v: v if v is None else _validate_authors(v))
    _v_year    = field_validator("published_year")(lambda cls, v: v if v is None else _validate_year(v))
    _v_genre   = field_validator("genre")(lambda cls, v: v if v is None else _validate_genre(v))


class BookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    authors: list[str]
    genre: str
    published_year: int
    created_at: datetime


class PaginatedBooks(BaseModel):
    items: list[BookOut]
    total: int
    limit: int
    offset: int


class UserCreate(BaseModel):
    username: Username
    password: Password


class UserOut(BaseModel):
    id: int
    username: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ImportReport(BaseModel):
    inserted: int
    failed: int
    errors: list[dict]