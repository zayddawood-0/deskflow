import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.db.base import Base
from app.db.session import get_db, normalize_database_url


def _env_file_value(key: str) -> str | None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return None


def _dev_database_url() -> str | None:
    url = os.environ.get("DATABASE_URL") or _env_file_value("DATABASE_URL")
    return normalize_database_url(url) if url else None


def _resolve_test_database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL") or _env_file_value("TEST_DATABASE_URL")
    if not url:
        raise RuntimeError(
            "TEST_DATABASE_URL is not set. Tests must never run against DATABASE_URL; "
            "add TEST_DATABASE_URL to backend/.env or export it in the environment."
        )
    resolved = normalize_database_url(url)
    if resolved == _dev_database_url():
        raise RuntimeError(
            "TEST_DATABASE_URL must point at a different database than DATABASE_URL."
        )
    return resolved


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
    dev_url = _dev_database_url()
    if dev_url is not None:
        assert str(eng.url) != dev_url, "tests must never run against the dev database"
    Base.metadata.create_all(eng)
    _seed_reference_data(eng)
    yield eng
    eng.dispose()


def _seed_reference_data(eng) -> None:
    with eng.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO sla_policies (priority, first_response_minutes, resolution_minutes)
                VALUES ('CRITICAL', 60, 240), ('HIGH', 240, 1440),
                       ('MEDIUM', 480, 2880), ('LOW', 1440, 4320)
                ON CONFLICT (priority) DO NOTHING
                """
            )
        )
        conn.execute(
            text(
                "INSERT INTO counters (name, value) VALUES ('ticket', 1040) "
                "ON CONFLICT (name) DO NOTHING"
            )
        )
        conn.execute(
            text(
                """
                CREATE OR REPLACE FUNCTION trg_audit_logs_immutable() RETURNS trigger AS $$
                BEGIN
                    RAISE EXCEPTION 'audit_logs is append-only: UPDATE/DELETE are not allowed';
                END;
                $$ LANGUAGE plpgsql
                """
            )
        )
        conn.execute(text("DROP TRIGGER IF EXISTS trg_audit_logs_immutable ON audit_logs"))
        conn.execute(
            text(
                """
                CREATE TRIGGER trg_audit_logs_immutable
                BEFORE UPDATE OR DELETE ON audit_logs
                FOR EACH ROW EXECUTE FUNCTION trg_audit_logs_immutable()
                """
            )
        )


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
