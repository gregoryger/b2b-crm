"""Интеграционные тесты API на отдельной тестовой БД PostgreSQL.

Запуск: docker compose run --rm backend sh -c "pip install --user -q pytest && python -m pytest -q"
"""
import os

os.environ.setdefault(
    "TEST_DATABASE_URL",
    f"postgresql+psycopg://{os.environ.get('POSTGRES_USER', 'crm')}:{os.environ.get('POSTGRES_PASSWORD', 'crm')}@db:5432/crm_test",
)
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ["REDIS_URL"] = os.environ.get("TEST_REDIS_URL", "redis://redis:6379/15")
os.environ["CELERY_ALWAYS_EAGER"] = "true"
os.environ["STORAGE_BACKEND"] = "local"
os.environ["LOCAL_STORAGE_PATH"] = "/tmp/crm-test-files"
os.environ["TELEPHONY_WEBHOOK_SECRET"] = "test-secret"

import pytest  # noqa: E402
import redis  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402


def _ensure_database():
    url = make_url(os.environ["DATABASE_URL"])
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": url.database})
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin.dispose()


@pytest.fixture(scope="session", autouse=True)
def database():
    _ensure_database()
    from app.db.base import Base
    from app.db.session import SessionLocal, engine
    import app.models  # noqa: F401
    from app.seed import seed_demo, seed_reference

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_reference(db)
        seed_demo(db)
        db.commit()
    redis.Redis.from_url(os.environ["REDIS_URL"]).flushdb()
    yield
    engine.dispose()


@pytest.fixture(scope="session")
def client(database):
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def isolated_rate_window(database):
    """Лимиты проверяются внутри теста, а не зависят от скорости предыдущих тестов."""
    from app.core.ratelimit import _memory

    r = redis.Redis.from_url(os.environ["REDIS_URL"])
    keys = list(r.scan_iter(match="rl:*"))
    if keys:
        r.delete(*keys)
    _memory.clear()


_tokens: dict[str, str] = {}


def login(client, email: str, password: str = "demo12345") -> str:
    if email not in _tokens:
        r = client.post("/api/v1/auth/login", json={"email": email, "password": password},
                        headers={"X-Real-IP": f"10.0.0.{len(_tokens) + 1}"})
        assert r.status_code == 200, r.text
        _tokens[email] = r.json()["access_token"]
    return _tokens[email]


class Api:
    def __init__(self, client, email):
        self.c = client
        self.h = {"Authorization": f"Bearer {login(client, email)}"}

    def get(self, url, **kw):
        return self.c.get(f"/api/v1{url}", headers=self.h, **kw)

    def post(self, url, **kw):
        return self.c.post(f"/api/v1{url}", headers=self.h, **kw)

    def patch(self, url, **kw):
        return self.c.patch(f"/api/v1{url}", headers=self.h, **kw)

    def delete(self, url, **kw):
        return self.c.delete(f"/api/v1{url}", headers=self.h, **kw)


@pytest.fixture(scope="session")
def head(client):
    return Api(client, "head@demo.ru")


@pytest.fixture(scope="session")
def manager(client):
    return Api(client, "petrov@demo.ru")


@pytest.fixture(scope="session")
def manager2(client):
    return Api(client, "kozlova@demo.ru")


@pytest.fixture(scope="session")
def marketer(client):
    return Api(client, "marketer@demo.ru")


@pytest.fixture(scope="session")
def admin(client):
    return Api(client, "admin@demo.ru")
