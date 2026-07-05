"""Database engine + session helpers (SQLModel / SQLite)."""
from __future__ import annotations

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from .config import DATABASE_URL


def _normalize(url: str) -> str:
    # Hosts hand out postgres:// or postgresql:// — SQLAlchemy needs an explicit
    # driver; we bundle psycopg (v3).
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def _make_engine():
    url = _normalize(DATABASE_URL)
    if url.startswith("sqlite"):
        return create_engine(url, echo=False, connect_args={"check_same_thread": False})
    # pool_pre_ping avoids stale connections when a serverless function reuses a
    # warm instance after the DB dropped an idle connection.
    return create_engine(url, echo=False, pool_pre_ping=True)


engine = _make_engine()


def init_db() -> None:
    # Import models so SQLModel registers them before create_all.
    from . import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    # expire_on_commit=False keeps ORM attributes populated after a commit so
    # objects returned from endpoints serialize correctly (otherwise a later
    # commit in the same request — e.g. the audit log — expires them to {}).
    with Session(engine, expire_on_commit=False) as session:
        yield session
