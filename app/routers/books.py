import csv
import io
import json
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import ValidationError

from app.auth import get_current_user
from app.repositories import books as books_repo
from app.schemas import BookCreate, BookOut, BookUpdate, ImportReport, PaginatedBooks


def _stringify_ctx(errors: list[dict]) -> list[dict]:
    safe: list[dict] = []
    for err in errors:
        e = dict(err)
        ctx = e.get("ctx")
        if isinstance(ctx, dict):
            e["ctx"] = {k: (str(v) if isinstance(v, Exception) else v) for k, v in ctx.items()}
        safe.append(e)
    return safe

router = APIRouter(prefix="/books", tags=["books"])

SortField = Literal["id", "title", "published_year", "created_at", "author"]
SortDir = Literal["asc", "desc"]


@router.post("/", response_model=BookOut, status_code=status.HTTP_201_CREATED)
async def create_book(payload: BookCreate, _user: dict = Depends(get_current_user)) -> BookOut:
    row = await books_repo.create_book(
        title=payload.title,
        authors=payload.authors,
        genre=payload.genre,
        published_year=payload.published_year,
    )
    return BookOut(**row)


@router.get("/", response_model=PaginatedBooks)
async def list_books(
    title: str | None = None,
    author: str | None = None,
    genre: str | None = None,
    year_from: Annotated[int | None, Query(ge=1800)] = None,
    year_to: Annotated[int | None, Query(ge=1800)] = None,
    sort_by: SortField = "id",
    sort_dir: SortDir = "asc",
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginatedBooks:
    if year_from is not None and year_to is not None and year_from > year_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="year_from must be <= year_to",
        )
    rows, total = await books_repo.list_books(
        title=title,
        author=author,
        genre=genre,
        year_from=year_from,
        year_to=year_to,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )
    return PaginatedBooks(
        items=[BookOut(**r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{book_id}", response_model=BookOut)
async def get_book(book_id: int) -> BookOut:
    row = await books_repo.get_book(book_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="book not found")
    return BookOut(**row)


@router.patch("/{book_id}", response_model=BookOut)
async def update_book(
    book_id: int,
    payload: BookUpdate,
    _user: dict = Depends(get_current_user),
) -> BookOut:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="at least one field is required",
        )
    row = await books_repo.update_book(book_id, **updates)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="book not found")
    return BookOut(**row)


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(book_id: int, _user: dict = Depends(get_current_user)) -> None:
    ok = await books_repo.delete_book(book_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="book not found")


def _parse_csv_rows(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    rows: list[dict] = []
    for raw in reader:
        authors_field = (raw.get("authors") or raw.get("author") or "").strip()
        authors = [a.strip() for a in authors_field.split(";") if a.strip()]
        year_raw = (raw.get("published_year") or "").strip()
        try:
            year = int(year_raw) if year_raw else None
        except ValueError:
            year = year_raw  # let Pydantic surface the error
        rows.append(
            {
                "title": (raw.get("title") or "").strip(),
                "authors": authors,
                "genre": (raw.get("genre") or "").strip(),
                "published_year": year,
            }
        )
    return rows


def _parse_json_rows(text: str) -> list[dict]:
    data = json.loads(text)
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ValueError("JSON payload must be an object or an array of objects")
    return data


@router.post(
    "/import",
    response_model=ImportReport,
    status_code=status.HTTP_201_CREATED,
)
async def import_books(
    file: UploadFile = File(...),
    _user: dict = Depends(get_current_user),
) -> ImportReport:
    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file must be UTF-8 encoded",
        )

    filename = (file.filename or "").lower()
    content_type = (file.content_type or "").lower()
    try:
        if filename.endswith(".csv") or "csv" in content_type:
            rows = _parse_csv_rows(text)
        elif filename.endswith(".json") or "json" in content_type:
            rows = _parse_json_rows(text)
        else:
            # try JSON first then CSV
            try:
                rows = _parse_json_rows(text)
            except (ValueError, json.JSONDecodeError):
                rows = _parse_csv_rows(text)
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"could not parse file: {exc}",
        )

    inserted = 0
    errors: list[dict] = []
    for idx, row in enumerate(rows):
        try:
            book = BookCreate(**row)
        except ValidationError as exc:
            errors.append({"row": idx, "error": _stringify_ctx(exc.errors())})
            continue
        try:
            await books_repo.create_book(
                title=book.title,
                authors=book.authors,
                genre=book.genre,
                published_year=book.published_year,
            )
        except Exception as exc:  # pragma: no cover - defensive
            errors.append({"row": idx, "error": str(exc)})
            continue
        inserted += 1

    return ImportReport(inserted=inserted, failed=len(errors), errors=errors)