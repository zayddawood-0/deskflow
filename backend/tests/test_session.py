import pytest

from app.db.session import is_running_on_vercel, normalize_database_url


def test_normalize_upgrades_postgres_scheme_and_adds_ssl() -> None:
    assert (
        normalize_database_url("postgres://user:pass@db.example.com/deskflow")
        == "postgresql+psycopg2://user:pass@db.example.com/deskflow?sslmode=require"
    )


def test_normalize_upgrades_postgresql_scheme() -> None:
    assert (
        normalize_database_url("postgresql://user:pass@db.example.com/deskflow")
        == "postgresql+psycopg2://user:pass@db.example.com/deskflow?sslmode=require"
    )


def test_normalize_preserves_existing_query_and_appends_sslmode() -> None:
    assert (
        normalize_database_url(
            "postgres://user:pass@db.example.com/deskflow?channel_binding=require"
        )
        == "postgresql+psycopg2://user:pass@db.example.com/deskflow"
        "?channel_binding=require&sslmode=require"
    )


def test_normalize_respects_existing_sslmode() -> None:
    url = "postgresql+psycopg2://user:pass@db.example.com/deskflow?sslmode=verify-full"
    assert normalize_database_url(url) == url


def test_normalize_leaves_local_urls_untouched() -> None:
    url = "postgresql+psycopg2://deskflow:deskflow@localhost:5432/deskflow"
    assert normalize_database_url(url) == url


def test_normalize_strips_surrounding_whitespace() -> None:
    url = "  postgresql+psycopg2://deskflow:deskflow@localhost:5432/deskflow  "
    assert (
        normalize_database_url(url)
        == "postgresql+psycopg2://deskflow:deskflow@localhost:5432/deskflow"
    )


@pytest.mark.parametrize("value", ["", "   ", "\t\n"])
def test_normalize_rejects_empty_urls_with_clear_error(value: str) -> None:
    with pytest.raises(ValueError, match="DATABASE_URL is required"):
        normalize_database_url(value)


def test_is_running_on_vercel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    assert is_running_on_vercel() is True
    monkeypatch.delenv("VERCEL")
    assert is_running_on_vercel() is False
