"""§4 Mandatory Security Guardrails — enforced in code.

These are the safety-critical checks that make the range safe to operate:

  * Dummy-data enforcement — reject anything that looks like a real identity,
    real credential, real malware, or a routable/public network address.
  * Strict isolation — only RFC1918 private address space is allowed inside the
    lab; any public IP implies a real network map or internet routing and is
    rejected.
  * Kill switch / isolation flags — global exercise state read by the engine.

Failing a guardrail raises ``GuardrailViolation``; callers surface it as HTTP 422.
"""
from __future__ import annotations

import ipaddress
import re

from sqlmodel import Session

from .models import Setting

KILL_SWITCH_KEY = "kill_switch"
ISOLATION_KEY = "isolation_enforced"


class GuardrailViolation(Exception):
    """Raised when an action would violate a §4 safety guardrail."""


# --------------------------------------------------------------------------- #
# Dummy-data allowlists
# --------------------------------------------------------------------------- #
# Only private/loopback/documentation ranges may appear in the lab topology.
_ALLOWED_NETS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("198.51.100.0/24"),  # TEST-NET-2 (docs)
    ipaddress.ip_network("203.0.113.0/24"),   # TEST-NET-3 (docs)
]

# Personnel referenced in scenarios must be obvious dummies, not real people.
DUMMY_IDENTITY_ALLOWLIST = {
    "trainee-01", "trainee-02", "trainee-03",
    "blue-lead", "red-cell", "white-cell",
    "operator-a", "operator-b", "npc-user",
}

# Patterns that indicate someone tried to smuggle a real secret into a payload.
_CREDENTIAL_PATTERNS = [
    re.compile(r"BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY"),
    re.compile(r"AKIA[0-9A-Z]{16}"),                 # AWS access key id
    re.compile(r"password\s*[:=]\s*\S{6,}", re.I),   # inline real password
    re.compile(r"eyJ[A-Za-z0-9_-]{20,}\."),          # JWT-looking token
]

# No real malware. Scenario "attacks" must be one of these harmless dummies.
ALLOWED_EVENT_TYPES = {
    "portscan", "bruteforce", "phishing", "lateral_move",
    "ransomware",        # dummy self-encryption script only
    "data_exfil", "dns_tunnel", "ot_fault", "c2_jamming",
    "supply_chain_anomaly",
}


def validate_ip(ip: str) -> None:
    if not ip:
        return
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError as exc:
        raise GuardrailViolation(f"Invalid IP address: {ip!r}") from exc
    if not any(addr in net for net in _ALLOWED_NETS):
        raise GuardrailViolation(
            f"IP {ip} is public/routable. Only private RFC1918 or "
            "documentation ranges are allowed inside the isolated lab."
        )


def validate_identity(name: str) -> None:
    if name and name not in DUMMY_IDENTITY_ALLOWLIST:
        raise GuardrailViolation(
            f"Identity {name!r} is not on the dummy allowlist. Real personnel "
            "identities are forbidden in the range."
        )


def scan_for_secrets(text: str) -> None:
    for pat in _CREDENTIAL_PATTERNS:
        if pat.search(text or ""):
            raise GuardrailViolation(
                "Payload appears to contain a real credential/secret. Only "
                "dummy data is permitted."
            )


def validate_event_type(event_type: str) -> None:
    if event_type not in ALLOWED_EVENT_TYPES:
        raise GuardrailViolation(
            f"Event type {event_type!r} is not on the allowlist of harmless "
            f"dummy attacks: {sorted(ALLOWED_EVENT_TYPES)}"
        )


# --------------------------------------------------------------------------- #
# Global exercise-state flags
# --------------------------------------------------------------------------- #
def _get_flag(session: Session, key: str, default: bool) -> bool:
    row = session.get(Setting, key)
    if row is None:
        return default
    return row.value == "1"


def _set_flag(session: Session, key: str, value: bool) -> None:
    row = session.get(Setting, key)
    if row is None:
        row = Setting(key=key, value="1" if value else "0")
    else:
        row.value = "1" if value else "0"
    session.add(row)
    session.commit()


def is_kill_switch_engaged(session: Session) -> bool:
    return _get_flag(session, KILL_SWITCH_KEY, default=False)


def set_kill_switch(session: Session, engaged: bool) -> None:
    _set_flag(session, KILL_SWITCH_KEY, engaged)


def is_isolation_enforced(session: Session) -> bool:
    # Isolation is ON by default — the range is air-gapped unless explicitly
    # (and auditably) relaxed by an Admin.
    return _get_flag(session, ISOLATION_KEY, default=True)


def set_isolation(session: Session, enforced: bool) -> None:
    _set_flag(session, ISOLATION_KEY, enforced)


def require_not_killed(session: Session) -> None:
    if is_kill_switch_engaged(session):
        raise GuardrailViolation(
            "Emergency kill switch is engaged. All training activity is halted."
        )
