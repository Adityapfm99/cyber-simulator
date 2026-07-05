"""§4 Immutable audit log.

Every meaningful action is recorded as a row whose hash chains to the previous
row's hash: ``hash = sha256(prev_hash + canonical_fields)``. Tampering with or
deleting any row breaks the chain, which ``verify_chain`` detects. This gives a
tamper-evident record without requiring external infrastructure.
"""
from __future__ import annotations

import hashlib
import json

from sqlmodel import Session, select

from .models import AuditLog, as_utc


def _canonical(row: AuditLog) -> str:
    payload = {
        # Normalize to tz-aware UTC so the hash is stable across the DB
        # write/read boundary (SQLite drops tzinfo).
        "ts": as_utc(row.ts).isoformat(),
        "actor": row.actor,
        "action": row.action,
        "target": row.target,
        "details": row.details,
        "prev_hash": row.prev_hash,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def record(
    session: Session,
    actor: str,
    action: str,
    target: str = "",
    details: dict | None = None,
) -> AuditLog:
    last = session.exec(
        select(AuditLog).order_by(AuditLog.id.desc()).limit(1)
    ).first()
    prev_hash = last.hash if last else "GENESIS"

    row = AuditLog(
        actor=actor,
        action=action,
        target=target,
        details=json.dumps(details or {}, sort_keys=True, separators=(",", ":")),
        prev_hash=prev_hash,
    )
    row.hash = hashlib.sha256(_canonical(row).encode()).hexdigest()
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def verify_chain(session: Session) -> dict:
    """Re-hash the whole chain and report the first break, if any."""
    rows = session.exec(select(AuditLog).order_by(AuditLog.id.asc())).all()
    prev_hash = "GENESIS"
    for row in rows:
        if row.prev_hash != prev_hash:
            return {"ok": False, "broken_at": row.id, "reason": "prev_hash mismatch"}
        expected = hashlib.sha256(_canonical(row).encode()).hexdigest()
        if row.hash != expected:
            return {"ok": False, "broken_at": row.id, "reason": "hash mismatch"}
        prev_hash = row.hash
    return {"ok": True, "entries": len(rows)}
