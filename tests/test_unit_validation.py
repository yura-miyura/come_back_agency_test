from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas import BookCreate, BookUpdate


def _payload(**overrides):
    base = {
        "title": "The Pragmatic Programmer",
        "authors": ["Andy Hunt", "Dave Thomas"],
        "genre": "Non-Fiction",
        "published_year": 1999,
    }
    base.update(overrides)
    return base


def test_book_create_accepts_valid_payload():
    book = BookCreate(**_payload())
    assert book.title == "The Pragmatic Programmer"
    assert book.authors == ["Andy Hunt", "Dave Thomas"]


def test_book_create_rejects_empty_title():
    with pytest.raises(ValidationError):
        BookCreate(**_payload(title="   "))


def test_book_create_rejects_empty_authors_list():
    with pytest.raises(ValidationError):
        BookCreate(**_payload(authors=[]))


def test_book_create_rejects_blank_author_name():
    with pytest.raises(ValidationError):
        BookCreate(**_payload(authors=["   "]))


def test_book_create_dedupes_author_names_case_insensitive():
    book = BookCreate(**_payload(authors=["Jane Doe", "jane doe"]))
    assert book.authors == ["Jane Doe"]


def test_book_create_rejects_year_before_1800():
    with pytest.raises(ValidationError):
        BookCreate(**_payload(published_year=1799))


def test_book_create_rejects_future_year():
    future = datetime.now(timezone.utc).year + 1
    with pytest.raises(ValidationError):
        BookCreate(**_payload(published_year=future))


def test_book_create_rejects_unknown_genre():
    with pytest.raises(ValidationError):
        BookCreate(**_payload(genre="Cookbook"))


def test_book_update_allows_partial_fields():
    upd = BookUpdate(title="New Title")
    dumped = upd.model_dump(exclude_unset=True)
    assert dumped == {"title": "New Title"}


def test_book_update_validates_provided_year():
    with pytest.raises(ValidationError):
        BookUpdate(published_year=1700)


def test_book_update_allows_no_fields():
    # router-level check handles "must provide at least one"; schema itself should accept
    BookUpdate()
