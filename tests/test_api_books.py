import io
import json


def book_payload(**overrides):
    base = {
        "title": "Sapiens",
        "authors": ["Yuval Noah Harari"],
        "genre": "History",
        "published_year": 2011,
    }
    base.update(overrides)
    return base


async def test_create_requires_auth(client):
    r = await client.post("/books/", json=book_payload())
    assert r.status_code == 401


async def test_create_and_get_book(client, auth_headers):
    r = await client.post("/books/", json=book_payload(), headers=auth_headers)
    assert r.status_code == 201, r.text
    book = r.json()
    assert book["title"] == "Sapiens"
    assert book["authors"] == ["Yuval Noah Harari"]
    assert book["genre"] == "History"
    assert book["published_year"] == 2011

    r = await client.get(f"/books/{book['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == book["id"]


async def test_get_missing_book_returns_404(client):
    r = await client.get("/books/99999")
    assert r.status_code == 404


async def test_create_rejects_invalid_year(client, auth_headers):
    r = await client.post(
        "/books/",
        json=book_payload(published_year=1700),
        headers=auth_headers,
    )
    assert r.status_code == 422


async def test_create_rejects_unknown_genre(client, auth_headers):
    r = await client.post(
        "/books/",
        json=book_payload(genre="Cookbook"),
        headers=auth_headers,
    )
    assert r.status_code == 422


async def test_update_partial_fields(client, auth_headers):
    r = await client.post("/books/", json=book_payload(), headers=auth_headers)
    bid = r.json()["id"]
    r = await client.patch(
        f"/books/{bid}",
        json={"title": "Sapiens (Updated)"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["title"] == "Sapiens (Updated)"
    assert r.json()["authors"] == ["Yuval Noah Harari"]


async def test_update_replaces_authors(client, auth_headers):
    r = await client.post("/books/", json=book_payload(), headers=auth_headers)
    bid = r.json()["id"]
    r = await client.patch(
        f"/books/{bid}",
        json={"authors": ["Author A", "Author B"]},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert sorted(r.json()["authors"]) == ["Author A", "Author B"]


async def test_update_missing_returns_404(client, auth_headers):
    r = await client.patch("/books/99999", json={"title": "x"}, headers=auth_headers)
    assert r.status_code == 404


async def test_update_with_no_fields_400(client, auth_headers):
    r = await client.post("/books/", json=book_payload(), headers=auth_headers)
    bid = r.json()["id"]
    r = await client.patch(f"/books/{bid}", json={}, headers=auth_headers)
    assert r.status_code == 400


async def test_delete_requires_auth(client):
    r = await client.delete("/books/1")
    assert r.status_code == 401


async def test_delete_book(client, auth_headers):
    r = await client.post("/books/", json=book_payload(), headers=auth_headers)
    bid = r.json()["id"]
    r = await client.delete(f"/books/{bid}", headers=auth_headers)
    assert r.status_code == 204
    r = await client.get(f"/books/{bid}")
    assert r.status_code == 404


async def test_delete_missing_returns_404(client, auth_headers):
    r = await client.delete("/books/99999", headers=auth_headers)
    assert r.status_code == 404


async def _seed(client, auth_headers, items):
    ids = []
    for payload in items:
        r = await client.post("/books/", json=payload, headers=auth_headers)
        assert r.status_code == 201, r.text
        ids.append(r.json()["id"])
    return ids


async def test_list_filter_by_title_and_author(client, auth_headers):
    await _seed(
        client,
        auth_headers,
        [
            book_payload(title="Sapiens", authors=["Yuval Noah Harari"], published_year=2011),
            book_payload(title="Homo Deus", authors=["Yuval Noah Harari"], published_year=2016),
            book_payload(title="Dune", authors=["Frank Herbert"], genre="Fantasy", published_year=1965),
        ],
    )
    r = await client.get("/books/", params={"title": "sap"})
    assert r.status_code == 200
    titles = [b["title"] for b in r.json()["items"]]
    assert titles == ["Sapiens"]

    r = await client.get("/books/", params={"author": "Harari"})
    titles = sorted(b["title"] for b in r.json()["items"])
    assert titles == ["Homo Deus", "Sapiens"]


async def test_list_filter_by_genre_and_year_range(client, auth_headers):
    await _seed(
        client,
        auth_headers,
        [
            book_payload(title="Old", published_year=1900, genre="History"),
            book_payload(title="Mid", published_year=1980, genre="History"),
            book_payload(title="New", published_year=2020, genre="Science"),
        ],
    )
    r = await client.get(
        "/books/",
        params={"genre": "History", "year_from": 1950, "year_to": 2000},
    )
    titles = [b["title"] for b in r.json()["items"]]
    assert titles == ["Mid"]


async def test_list_year_range_validation(client, auth_headers):
    r = await client.get("/books/", params={"year_from": 2020, "year_to": 1990})
    assert r.status_code == 400


async def test_list_pagination_and_sort(client, auth_headers):
    await _seed(
        client,
        auth_headers,
        [
            book_payload(title="C", published_year=2001),
            book_payload(title="A", published_year=2003),
            book_payload(title="B", published_year=2002),
        ],
    )
    r = await client.get("/books/", params={"sort_by": "title", "sort_dir": "asc", "limit": 2, "offset": 0})
    body = r.json()
    assert body["total"] == 3
    assert [b["title"] for b in body["items"]] == ["A", "B"]
    r = await client.get("/books/", params={"sort_by": "title", "sort_dir": "asc", "limit": 2, "offset": 2})
    assert [b["title"] for b in r.json()["items"]] == ["C"]

    r = await client.get("/books/", params={"sort_by": "published_year", "sort_dir": "desc"})
    years = [b["published_year"] for b in r.json()["items"]]
    assert years == sorted(years, reverse=True)


async def test_import_json(client, auth_headers):
    data = [
        book_payload(title="A", published_year=2001),
        book_payload(title="B", published_year=2002),
        book_payload(title="Bad", published_year=1700),  # invalid
    ]
    files = {"file": ("books.json", json.dumps(data), "application/json")}
    r = await client.post("/books/import", files=files, headers=auth_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["inserted"] == 2
    assert body["failed"] == 1

    r = await client.get("/books/")
    assert r.json()["total"] == 2


async def test_import_csv(client, auth_headers):
    # columns are comma-separated; multiple authors within the `authors` column are joined with ';'
    csv_text = (
        "title,authors,genre,published_year\n"
        '"Foundation","Isaac Asimov","Fiction","1951"\n'
        '"Anthology","Asimov;Clarke","Fiction","1973"\n'
    )
    files = {"file": ("books.csv", csv_text, "text/csv")}
    r = await client.post("/books/import", files=files, headers=auth_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["inserted"] == 2
    assert body["failed"] == 0

    r = await client.get("/books/", params={"author": "Asimov"})
    assert r.json()["total"] == 2


async def test_import_requires_auth(client):
    files = {"file": ("x.json", "[]", "application/json")}
    r = await client.post("/books/import", files=files)
    assert r.status_code == 401