import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def _test_env() -> None:
    os.environ.setdefault("APP_ENV", "development")
    os.environ.setdefault("SECRET_KEY", "test-only-secret-key-not-used-in-prod-0123456789")
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+psycopg2://deskflow:deskflow@localhost:5432/deskflow",
    )


@pytest.fixture()
def client() -> TestClient:
    from app.main import create_app

    return TestClient(create_app())
