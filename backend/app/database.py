"""Database engine + session helpers (SQLModel / SQLite)."""
from __future__ import annotations

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from .config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)


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
