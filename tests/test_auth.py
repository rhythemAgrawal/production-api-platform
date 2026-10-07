import pytest

from backend.app.database import engine

CREDENTIALS = {"username": "alice", "password": "correct horse battery staple"}

needs_postgres = pytest.mark.skipif(
    engine.dialect.name == "sqlite",
    reason="SQLite drops the timezone on expires_at; set TEST_DATABASE_URL to Postgres",
)


def test_signup_returns_201_with_tokens(client):
    response = client.post("/signup", json=CREDENTIALS)

    assert response.status_code == 201
    assert response.json()["username"] == "alice"
    assert response.json()["access_token"]
    assert "refresh_token" in response.cookies


def test_duplicate_signup_returns_409(client):
    client.post("/signup", json=CREDENTIALS)
    response = client.post("/signup", json=CREDENTIALS)

    assert response.status_code == 409


def test_login_succeeds_with_right_password(client):
    client.post("/signup", json=CREDENTIALS)
    response = client.post("/login", json=CREDENTIALS)

    assert response.status_code == 200
    assert response.json()["access_token"]


def test_login_with_wrong_password_returns_401(client):
    client.post("/signup", json=CREDENTIALS)
    response = client.post("/login", json={**CREDENTIALS, "password": "wrong"})

    assert response.status_code == 401


def test_login_with_unknown_username_returns_401(client):
    response = client.post("/login", json=CREDENTIALS)

    assert response.status_code == 401


def test_items_require_an_access_token(client):
    assert client.get("/items").status_code == 401

    token = client.post("/signup", json=CREDENTIALS).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post("/items", json={"name": "widget"}, headers=headers)
    assert created.status_code == 201

    listed = client.get("/items", headers=headers)
    assert [item["name"] for item in listed.json()] == ["widget"]


@needs_postgres
def test_refresh_rotates_the_token_and_reuse_revokes_the_session(client):
    client.post("/signup", json=CREDENTIALS)
    old_token = client.cookies["refresh_token"]

    assert client.post("/refresh").status_code == 200
    new_token = client.cookies["refresh_token"]
    assert new_token != old_token

    # Replaying the old token looks like theft: every token for the user is revoked.
    client.cookies.set("refresh_token", old_token)
    assert client.post("/refresh").status_code == 401

    client.cookies.set("refresh_token", new_token)
    assert client.post("/refresh").status_code == 401
