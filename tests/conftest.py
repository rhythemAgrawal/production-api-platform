import os
import tempfile
from pathlib import Path

import pytest
import redis
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# backend.config reads its settings at import time, so the environment has
# to be in place before anything from backend is imported.
_tmp = Path(tempfile.mkdtemp(prefix="api-platform-tests-"))
_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

(_tmp / "private.pem").write_bytes(_key.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
))
(_tmp / "public.pem").write_bytes(_key.public_key().public_bytes(
    serialization.Encoding.PEM,
    serialization.PublicFormat.SubjectPublicKeyInfo,
))

os.environ.update({
    # SQLite by default so the auth tests need no services. Point
    # TEST_DATABASE_URL at Postgres to also run the refresh-token tests.
    "DATABASE_URL": os.environ.get("TEST_DATABASE_URL", f"sqlite:///{_tmp / 'test.db'}"),
    "REDIS_URL": os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15"),
    "JWT_PRIVATE_KEY_PATH": str(_tmp / "private.pem"),
    "JWT_PUBLIC_KEY_PATH": str(_tmp / "public.pem"),
    "OTEL_EXPORTER_OTLP_ENDPOINT": "localhost:4320",
    "OTEL_SDK_DISABLED": "true",
    "APP_NAME": "api-platform-tests",
    "ENVIRONMENT": "test",
})

from fastapi.testclient import TestClient

from backend.app.database import Base, engine, redis_client
from backend.app.main import app


def clear_rate_limits():
    try:
        for key in redis_client.scan_iter("rate_limit:*"):
            redis_client.delete(key)
    except redis.exceptions.ConnectionError:
        return False

    return True


@pytest.fixture(autouse=True)
def fresh_state():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    clear_rate_limits()
    yield
    clear_rate_limits()


@pytest.fixture
def client():
    # https, because the refresh cookie is Secure and would not be sent back over http.
    return TestClient(app, base_url="https://testserver")


@pytest.fixture
def redis_available():
    if not clear_rate_limits():
        pytest.skip("Redis is not reachable")
