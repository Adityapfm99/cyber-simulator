"""MOD-02 — Web Security Lab.

A self-contained, deliberately-vulnerable training web app covering common OWASP
Top 10 classes. The blue team's job is to **detect and patch** each vulnerability.

SAFETY: every "vulnerability" operates only on throwaway dummy data held in this
module. Nothing here touches the real platform database, the OS, or the
filesystem — e.g. the "command injection" endpoint never executes a shell command,
it returns a canned simulated result. Each vulnerability can be toggled to a
*patched* (secure) implementation to drill remediation. This is an authorized,
air-gapped training lab; all data is fake.

Each exploit attempt is logged (WebSecAttempt) and mirrored into the SOC/SIEM feed
of the active scenario so analysts can spot it.
"""
from __future__ import annotations

import html
import re
import sqlite3

from sqlmodel import Session, select

from . import audit
from .models import LogEntry, Scenario, ScenarioStatus, WebSecAttempt

# --------------------------------------------------------------------------- #
# Vulnerability registry
# --------------------------------------------------------------------------- #
VULNS = [
    {
        "id": "sqli",
        "name": "SQL Injection (login bypass)",
        "owasp": "A03:2021 – Injection",
        "endpoint": "POST /api/lab/websec/login",
        "hint": "Coba username: admin'-- atau ' OR '1'='1",
    },
    {
        "id": "xss",
        "name": "Reflected Cross-Site Scripting",
        "owasp": "A03:2021 – Injection (XSS)",
        "endpoint": "GET /api/lab/websec/search?q=",
        "hint": "Coba q=<script>alert(1)</script>",
    },
    {
        "id": "idor",
        "name": "Broken Access Control (IDOR)",
        "owasp": "A01:2021 – Broken Access Control",
        "endpoint": "GET /api/lab/websec/invoice/{id}?as_user=",
        "hint": "Akses invoice milik user lain, mis. /invoice/3?as_user=trainee-01",
    },
    {
        "id": "cmdi",
        "name": "Command Injection (disimulasikan)",
        "owasp": "A03:2021 – Injection (OS Command)",
        "endpoint": "GET /api/lab/websec/ping?host=",
        "hint": "Coba host=127.0.0.1;id — hasil disimulasikan, tidak menjalankan shell",
    },
    {
        "id": "exposure",
        "name": "Sensitive Data Exposure (debug endpoint)",
        "owasp": "A05:2021 – Security Misconfiguration",
        "endpoint": "GET /api/lab/websec/debug",
        "hint": "Endpoint debug membocorkan konfigurasi/secret dummy",
    },
]
_VULN_IDS = {v["id"] for v in VULNS}

# --------------------------------------------------------------------------- #
# Sandboxed dummy data (NEVER real)
# --------------------------------------------------------------------------- #
_DUMMY_USERS = [
    ("admin", "s3cr3t-DUMMY", "admin"),
    ("trainee-01", "pass123-DUMMY", "user"),
    ("blue-lead", "bluelead-DUMMY", "user"),
]
_DUMMY_INVOICES = {
    1: {"owner": "trainee-01", "amount": 1500, "note": "training invoice #1 (DUMMY)"},
    2: {"owner": "blue-lead", "amount": 3200, "note": "training invoice #2 (DUMMY)"},
    3: {"owner": "admin", "amount": 9999, "note": "CONFIDENTIAL flag-DUMMY-{idor_pwned}"},
}
_DUMMY_CONFIG = {
    "app": "webseclab", "env": "training",
    "db_password": "DUMMY-not-a-real-password",
    "api_key": "DUMMY-AKIA-0000-TRAINING-ONLY",
    "note": "Semua nilai di sini palsu untuk latihan.",
}


class WebSecError(Exception):
    """Raised for a blocked/patched request (surfaced as HTTP 403)."""


# --------------------------------------------------------------------------- #
# Patch state (persisted in Setting so it survives across serverless requests)
# --------------------------------------------------------------------------- #
def _key(vuln_id: str) -> str:
    return f"webseclab:{vuln_id}:patched"


def is_patched(session: Session, vuln_id: str) -> bool:
    from .models import Setting
    row = session.get(Setting, _key(vuln_id))
    return bool(row and row.value == "1")


def set_patched(session: Session, actor: str, vuln_id: str, patched: bool) -> None:
    from .models import Setting
    if vuln_id not in _VULN_IDS:
        raise WebSecError(f"Unknown vulnerability: {vuln_id!r}")
    k = _key(vuln_id)
    row = session.get(Setting, k)
    if row is None:
        row = Setting(key=k, value="1" if patched else "0")
    else:
        row.value = "1" if patched else "0"
    session.add(row)
    session.commit()
    audit.record(session, actor, "webseclab.patch", vuln_id, {"patched": patched})


# --------------------------------------------------------------------------- #
# Attempt logging + SOC mirroring
# --------------------------------------------------------------------------- #
def _record(session: Session, vuln_id: str, payload: str, success: bool,
            src_ip: str, detail: str) -> None:
    session.add(WebSecAttempt(
        vuln_id=vuln_id, payload=payload[:500], success=success,
        src_ip=src_ip or "10.66.66.66", detail=detail[:500],
    ))
    # Mirror into the SOC feed of the most recent running scenario, if any.
    sc = session.exec(
        select(Scenario).where(Scenario.status == ScenarioStatus.RUNNING)
        .order_by(Scenario.id.desc())
    ).first()
    if sc is not None:
        sev = "critical" if success else "notice"
        verb = "SUCCESS" if success else "blocked"
        session.add(LogEntry(
            scenario_id=sc.id, source="waf", severity=sev,
            src_ip=src_ip or "10.66.66.66", dst_ip="10.10.1.10",
            message=f"webseclab {vuln_id} attempt {verb} payload={payload[:80]!r}",
        ))
    session.commit()


# --------------------------------------------------------------------------- #
# Vulnerable (and patched) implementations — all sandboxed
# --------------------------------------------------------------------------- #
def login(session: Session, username: str, password: str, src_ip: str = "") -> dict:
    patched = is_patched(session, "sqli")
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE users(username TEXT, password TEXT, role TEXT)")
    con.executemany("INSERT INTO users VALUES (?,?,?)", _DUMMY_USERS)

    if patched:
        rows = con.execute(
            "SELECT username, role FROM users WHERE username=? AND password=?",
            (username, password),
        ).fetchall()
    else:
        # VULNERABLE: string-concatenated query on isolated in-memory dummy DB.
        query = ("SELECT username, role FROM users "
                 f"WHERE username='{username}' AND password='{password}'")
        try:
            rows = con.execute(query).fetchall()
        except sqlite3.Error as exc:
            rows = []
            _record(session, "sqli", f"{username}|{password}", False, src_ip, str(exc))
            con.close()
            return {"authenticated": False, "error": "sql error", "patched": patched}
    con.close()

    # Success as an *exploit* = the injection returned users without valid creds.
    legit = any(u == username and p == password for u, p, _ in _DUMMY_USERS)
    exploited = (not patched) and bool(rows) and not legit
    _record(session, "sqli", f"{username}|{password}", exploited, src_ip,
            f"rows={len(rows)}")
    return {
        "authenticated": bool(rows),
        "patched": patched,
        "exploited": exploited,
        "leaked_accounts": [r[0] for r in rows] if exploited else (
            [rows[0][0]] if rows else []),
    }


def search(session: Session, q: str, src_ip: str = "") -> dict:
    patched = is_patched(session, "xss")
    if patched:
        body = f"<p>Hasil pencarian untuk: {html.escape(q)}</p>"
        exploited = False
    else:
        body = f"<p>Hasil pencarian untuk: {q}</p>"  # VULNERABLE: unescaped
        exploited = bool(re.search(r"<\s*script|onerror\s*=|<\s*img", q, re.I))
    _record(session, "xss", q, exploited, src_ip, f"reflected={not patched}")
    return {"patched": patched, "exploited": exploited, "html": body}


def invoice(session: Session, invoice_id: int, as_user: str, src_ip: str = "") -> dict:
    patched = is_patched(session, "idor")
    inv = _DUMMY_INVOICES.get(invoice_id)
    if inv is None:
        _record(session, "idor", f"id={invoice_id} as={as_user}", False, src_ip, "404")
        raise WebSecError("Invoice not found")
    owns = inv["owner"] == as_user
    if patched and not owns:
        _record(session, "idor", f"id={invoice_id} as={as_user}", False, src_ip,
                "access denied")
        raise WebSecError("Akses ditolak — bukan pemilik invoice.")
    exploited = (not patched) and (not owns)
    note = inv["note"].replace("{idor_pwned}", "IDOR-PWNED" if exploited else "xxxx")
    _record(session, "idor", f"id={invoice_id} as={as_user}", exploited, src_ip,
            f"owner={inv['owner']}")
    return {"patched": patched, "exploited": exploited,
            "invoice": {**inv, "note": note, "id": invoice_id}}


_HOST_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def ping(session: Session, host: str, src_ip: str = "") -> dict:
    """SIMULATED ping. Never runs a real command."""
    patched = is_patched(session, "cmdi")
    has_meta = bool(re.search(r"[;&|`$><\n]", host))
    if patched and not _HOST_RE.match(host):
        _record(session, "cmdi", host, False, src_ip, "rejected invalid host")
        raise WebSecError("Host tidak valid — karakter berbahaya ditolak.")
    output = f"PING {host}: 64 bytes, time=0.3 ms (DUMMY)"
    exploited = (not patched) and has_meta
    if exploited:
        # Canned, fake "injected command" output — nothing is executed.
        output += "\nuid=0(root-DUMMY) gid=0(root) groups=0(root)  [SIMULATED]"
    _record(session, "cmdi", host, exploited, src_ip, f"meta={has_meta}")
    return {"patched": patched, "exploited": exploited, "output": output}


def debug(session: Session, src_ip: str = "") -> dict:
    patched = is_patched(session, "exposure")
    if patched:
        _record(session, "exposure", "/debug", False, src_ip, "403")
        raise WebSecError("Debug endpoint dinonaktifkan.")
    _record(session, "exposure", "/debug", True, src_ip, "config leaked")
    return {"patched": patched, "exploited": True, "config": _DUMMY_CONFIG}


# --------------------------------------------------------------------------- #
# Registry / scoreboard
# --------------------------------------------------------------------------- #
def registry(session: Session) -> dict:
    items = []
    patched_count = 0
    for v in VULNS:
        p = is_patched(session, v["id"])
        patched_count += int(p)
        attempts = session.exec(
            select(WebSecAttempt).where(WebSecAttempt.vuln_id == v["id"])
        ).all()
        items.append({
            **v,
            "patched": p,
            "attempts": len(attempts),
            "successful_exploits": sum(1 for a in attempts if a.success),
        })
    total = len(VULNS)
    return {
        "vulnerabilities": items,
        "total": total,
        "patched": patched_count,
        "hardening_score": round(100 * patched_count / total) if total else 0,
    }


def recent_attempts(session: Session, limit: int = 50) -> list[WebSecAttempt]:
    rows = session.exec(
        select(WebSecAttempt).order_by(WebSecAttempt.id.desc()).limit(limit)
    ).all()
    return list(rows)
