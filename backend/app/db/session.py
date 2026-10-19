import os
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings


def normalize_database_url(url: str) -> str:
    """Return a SQLAlchemy-ready URL. Pure function: no I/O, no global state, no mutation."""
    cleaned = url.strip()
    if not cleaned:
        raise ValueError(
            "DATABASE_URL is required and must not be empty. Set it in the environment "
            "(or backend/.env); on Vercel it must be Neon's POOLED connection string."
        )
    if cleaned.startswith("postgres://"):
        cleaned = "postgresql+psycopg2://" + cleaned.removeprefix("postgres://")
    elif cleaned.startswith("postgresql://"):
        cleaned = "postgresql+psycopg2://" + cleaned.removeprefix("postgresql://")
    if "sslmode=" not in cleaned and "@localhost" not in cleaned and "@127.0.0.1" not in cleaned:
        cleaned += ("&" if "?" in cleaned else "?") + "sslmode=require"
    return cleaned


def is_running_on_vercel() -> bool:
    return os.environ.get("VERCEL") == "1"


def create_db_engine() -> Engine:
    poolclass = NullPool if is_running_on_vercel() else None
    return create_engine(
        normalize_database_url(get_settings().database_url),
        pool_pre_ping=True,
        poolclass=poolclass,
    )


engine: Engine = create_db_engine()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def database_is_up(db: Session) -> bool:
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
