import pytest


async def test_register_and_login(client):
    r = await client.post(
        "/auth/register",
        json={"username": "alice", "password": "supersecret1"},
    )
    assert r.status_code == 201
    assert r.json() == {"id": 1, "username": "alice"} or r.json()["username"] == "alice"

    r = await client.post(
        "/auth/login",
        data={"username": "alice", "password": "supersecret1"},
    )
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"
    assert r.json()["access_token"]


async def test_register_duplicate_username_conflict(client):
    body = {"username": "bob", "password": "supersecret1"}
    r = await client.post("/auth/register", json=body)
    assert r.status_code == 201
    r = await client.post("/auth/register", json=body)
    assert r.status_code == 409


async def test_login_with_wrong_password(client):
    await client.post(
        "/auth/register",
        json={"username": "carol", "password": "supersecret1"},
    )
    r = await client.post(
        "/auth/login",
        data={"username": "carol", "password": "wrong-password"},
    )
    assert r.status_code == 401


async def test_login_unknown_user(client):
    r = await client.post(
        "/auth/login",
        data={"username": "nobody", "password": "supersecret1"},
    )
    assert r.status_code == 401


async def test_register_rejects_short_password(client):
    r = await client.post(
        "/auth/register",
        json={"username": "dave", "password": "short"},
    )
    assert r.status_code == 422