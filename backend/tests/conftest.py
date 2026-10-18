import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.db.base import Base
from app.db.session import get_db, normalize_database_url

DEFAULT_TEST_URL = "postgresql+psycopg2://deskflow:deskflow@localhost:5432/deskflow_test"


def _env_file_value(key: str) -> str | None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return None


def _resolve_test_database_url() -> str:
    url = (
        os.environ.get("TEST_DATABASE_URL")
        or _env_file_value("TEST_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or _env_file_value("DATABASE_URL")
        or DEFAULT_TEST_URL
    )
    return normalize_database_url(url)


@pytest.fixture(scope="session", autouse=True)
def _test_env() -> None:
    os.environ.setdefault("APP_ENV", "development")
    os.environ.setdefault("SECRET_KEY", "test-only-secret-key-not-used-in-prod-0123456789")
    os.environ["DATABASE_URL"] = _resolve_test_database_url()
    from app.core.config import get_settings

    get_settings.cache_clear()


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True, poolclass=NullPool)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def connection(engine):
    conn = engine.connect()
    trans = conn.begin()
    yield conn
    trans.rollback()
    conn.close()


@pytest.fixture()
def db(connection):
    session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
        autoflush=False,
        expire_on_commit=False,
    )
    yield session
    session.rollback()
    session.close()


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    from app.core.rate_limit import limiter

    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture()
def client(db):
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def raw_connection(engine):
    """Direct connection for tests that need raw SQL outside the app session."""
    conn = engine.connect()
    yield conn
    conn.close()


def exec_sql(connection, statement: str, **params: object) -> None:
    connection.execute(text(statement), params)
