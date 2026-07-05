"""Seed demo users and a starter scenario.

Run once: ``uv run python -m app.seed``  (idempotent — safe to re-run).
"""
from __future__ import annotations

from sqlmodel import Session, select

from .auth import hash_password
from .database import engine, init_db
from .models import Role, User

_DEMO_USERS = [
    ("admin", "admin123", Role.ADMIN),
    ("director", "director123", Role.DIRECTOR),
    ("commander", "commander123", Role.COMMANDER),
    ("analyst", "analyst123", Role.ANALYST),
    ("observer", "observer123", Role.OBSERVER),
]


def seed(verbose: bool = True) -> None:
    init_db()
    created = 0
    with Session(engine) as session:
        for username, password, role in _DEMO_USERS:
            existing = session.exec(
                select(User).where(User.username == username)
            ).first()
            if existing:
                continue
            hashed, salt = hash_password(password)
            session.add(User(
                username=username, hashed_password=hashed, salt=salt, role=role,
            ))
            created += 1
        session.commit()
    if not verbose:
        return
    print(f"Seeded {created} new demo user(s):")
    for username, password, role in _DEMO_USERS:
        print(f"  {role.value:<18} {username} / {password}")
    print("\nStart the API:  uv run uvicorn app.main:app --reload --port 8000")


if __name__ == "__main__":
    seed()
