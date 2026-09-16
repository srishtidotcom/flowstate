"""SQLAlchemy engine and transaction boundary."""

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def database_url() -> str:
    explicit_url = os.getenv("DATABASE_URL")
    if explicit_url:
        return explicit_url

    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    name = os.getenv("POSTGRES_DB", "flowstate")
    user = os.getenv("POSTGRES_USER", "flowstate_user")
    password = os.getenv("POSTGRES_PASSWORD", "flowstate123")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"


DATABASE_URL = database_url()
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(
    DATABASE_URL,
    future=True,
    pool_pre_ping=not DATABASE_URL.startswith("sqlite"),
    connect_args=_connect_args,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Provide one transaction and commit only at the service boundary."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency with the same transaction semantics as get_db()."""
    with get_db() as db:
        yield db
