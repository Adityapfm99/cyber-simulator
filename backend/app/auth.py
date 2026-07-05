"""Authentication + RBAC.

Password hashing (PBKDF2-HMAC-SHA256) and signed tokens (HMAC-SHA256) use only
the Python standard library — no external crypto dependency to vet, which suits
an air-gapped deployment.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select

from .config import SECRET_KEY, TOKEN_TTL_SECONDS
from .database import get_session
from .models import Role, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

_PBKDF2_ROUNDS = 200_000


# --------------------------------------------------------------------------- #
# Passwords
# --------------------------------------------------------------------------- #
def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    if salt is None:
        salt = base64.urlsafe_b64encode(hashlib.sha256(
            (password + str(time.time_ns())).encode()
        ).digest()[:16]).decode()
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _PBKDF2_ROUNDS)
    return base64.urlsafe_b64encode(dk).decode(), salt


def verify_password(password: str, hashed: str, salt: str) -> bool:
    candidate, _ = hash_password(password, salt)
    return hmac.compare_digest(candidate, hashed)


# --------------------------------------------------------------------------- #
# Tokens — compact signed JSON (a minimal JWT-alike)
# --------------------------------------------------------------------------- #
def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64d(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def create_token(username: str, role: str) -> str:
    payload = {"sub": username, "role": role, "exp": int(time.time()) + TOKEN_TTL_SECONDS}
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64(hmac.new(SECRET_KEY.encode(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def decode_token(token: str) -> dict:
    try:
        body, sig = token.split(".")
    except ValueError as exc:
        raise ValueError("malformed token") from exc
    expected = _b64(hmac.new(SECRET_KEY.encode(), body.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        raise ValueError("bad signature")
    payload = json.loads(_b64d(body))
    if payload.get("exp", 0) < int(time.time()):
        raise ValueError("token expired")
    return payload


# --------------------------------------------------------------------------- #
# Dependencies
# --------------------------------------------------------------------------- #
def authenticate(session: Session, username: str, password: str) -> User | None:
    user = session.exec(select(User).where(User.username == username)).first()
    if not user or not user.active:
        return None
    if not verify_password(password, user.hashed_password, user.salt):
        return None
    return user


def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    creds_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
    except ValueError:
        raise creds_error
    user = session.exec(
        select(User).where(User.username == payload["sub"])
    ).first()
    if not user or not user.active:
        raise creds_error
    return user


def require_roles(*roles: Role) -> Callable[[User], User]:
    """Dependency factory enforcing that the caller holds one of ``roles``."""

    allowed = set(roles)

    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role {user.role} not permitted for this action. "
                       f"Requires one of: {[r.value for r in allowed]}",
            )
        return user

    return _dep
