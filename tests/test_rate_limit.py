import pytest

from backend.app import middlewares
from backend.app.services import check_rate_limit
from backend.config import get_rate_limit_config

LOGIN_CAPACITY = get_rate_limit_config("/login").capacity


def test_bucket_allows_capacity_then_rejects(redis_available):
    config = get_rate_limit_config("/login")
    results = [check_rate_limit("user-1", "/login", config) for _ in range(LOGIN_CAPACITY + 1)]

    assert [allowed for allowed, _ in results] == [True] * LOGIN_CAPACITY + [False]

    _, headers = results[-1]
    assert headers["X-RateLimit-Remaining"] == "0"
    assert int(headers["Retry-After"]) >= 1


def test_paths_with_their_own_rule_do_not_share_a_bucket(redis_available):
    for _ in range(LOGIN_CAPACITY + 1):
        check_rate_limit("user-1", "/login", get_rate_limit_config("/login"))

    allowed, _ = check_rate_limit("user-1", "/health", get_rate_limit_config("/health"))
    assert allowed


def test_requests_over_the_limit_get_429(client, redis_available):
    credentials = {"username": "nobody", "password": "x"}
    codes = [client.post("/login", json=credentials).status_code for _ in range(LOGIN_CAPACITY + 1)]

    assert codes == [401] * LOGIN_CAPACITY + [429]

    response = client.post("/login", json=credentials)
    assert int(response.headers["Retry-After"]) >= 1


def test_allowed_responses_carry_the_remaining_count(client, redis_available):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["X-RateLimit-Remaining"] == "99"


def test_limiter_fails_open_when_redis_is_down(client, monkeypatch):
    def broken(*args):
        raise ConnectionError("redis is down")

    monkeypatch.setattr(middlewares, "check_rate_limit", broken)

    assert client.get("/health").status_code == 200
