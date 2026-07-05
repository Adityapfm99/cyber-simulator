"""Data models for the cyber-range platform.

All timestamps are stored as timezone-aware UTC datetimes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(dt: datetime | None) -> datetime | None:
    """Coerce a datetime to tz-aware UTC.

    SQLite drops tzinfo, so values read back from the DB are naive. We treat a
    naive datetime as UTC (that is how we always write them) and return a
    tz-aware value, making arithmetic and serialization stable across the
    write/read boundary.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# --------------------------------------------------------------------------- #
# §4 RBAC — five distinct roles with separated duties.
# --------------------------------------------------------------------------- #
class Role(str, Enum):
    ADMIN = "Admin"                      # platform + guardrail administration
    DIRECTOR = "Exercise Director"       # designs/runs exercises, injects events
    COMMANDER = "Commander"              # leadership view, C2 dashboard
    ANALYST = "SOC Analyst"              # detects/triages/contains incidents
    OBSERVER = "Observer"                # read-only


class ScenarioStatus(str, Enum):
    DRAFT = "draft"
    DEPLOYING = "deploying"
    RUNNING = "running"
    HALTED = "halted"          # kill switch engaged
    DESTROYED = "destroyed"


class NodeStatus(str, Enum):
    PROVISIONING = "provisioning"
    UP = "up"
    COMPROMISED = "compromised"
    QUARANTINED = "quarantined"
    HALTED = "halted"
    DESTROYED = "destroyed"


class IncidentStatus(str, Enum):
    OPEN = "open"
    DETECTED = "detected"
    TRIAGED = "triaged"
    CONTAINED = "contained"
    RECOVERED = "recovered"


# --------------------------------------------------------------------------- #
# Core tables
# --------------------------------------------------------------------------- #
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    hashed_password: str
    salt: str
    role: Role
    active: bool = True
    created_at: datetime = Field(default_factory=utcnow)


class AuditLog(SQLModel, table=True):
    """Append-only, hash-chained tamper-evident log (§4)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=utcnow, index=True)
    actor: str                       # username
    action: str                      # e.g. "scenario.deploy"
    target: str = ""                 # affected object
    details: str = ""                # JSON string
    prev_hash: str = ""
    hash: str = ""                   # sha256(prev_hash + canonical row)


class Scenario(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    template: str
    description: str = ""
    status: ScenarioStatus = ScenarioStatus.DRAFT
    created_by: str = ""
    created_at: datetime = Field(default_factory=utcnow)
    deployed_at: Optional[datetime] = None
    destroyed_at: Optional[datetime] = None


class Node(SQLModel, table=True):
    """A simulated VM/container in the lab topology."""

    id: Optional[int] = Field(default=None, primary_key=True)
    scenario_id: int = Field(index=True, foreign_key="scenario.id")
    name: str
    kind: str                        # vm | container | ot | c2 | vendor
    role: str = ""                   # e.g. "web", "db", "hmi", "firewall"
    ip: str = ""                     # must be RFC1918 (guardrail-enforced)
    status: NodeStatus = NodeStatus.PROVISIONING


class Edge(SQLModel, table=True):
    """A topology link between two nodes."""

    id: Optional[int] = Field(default=None, primary_key=True)
    scenario_id: int = Field(index=True, foreign_key="scenario.id")
    src: str                         # node name
    dst: str                         # node name


class Event(SQLModel, table=True):
    """An injected exercise event (attack, fault, or environmental)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    scenario_id: int = Field(index=True, foreign_key="scenario.id")
    type: str                        # e.g. "ransomware", "portscan", "ot_fault"
    title: str
    target_node: str = ""
    payload: str = ""                # JSON string (dummy params only)
    scheduled_at: Optional[datetime] = None
    injected_at: Optional[datetime] = None
    injected_by: str = ""
    status: str = "pending"          # pending | injected | cancelled


class LogEntry(SQLModel, table=True):
    """A simulated SIEM log line (§3 SOC Simulator)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    scenario_id: int = Field(index=True, foreign_key="scenario.id")
    ts: datetime = Field(default_factory=utcnow, index=True)
    source: str                      # firewall | edr | dns | proxy
    severity: str                    # info | notice | warning | critical
    src_ip: str = ""
    dst_ip: str = ""
    message: str = ""
    event_id: Optional[int] = None   # set when this log belongs to an attack


class Incident(SQLModel, table=True):
    """Tracks the response lifecycle for scoring (§2)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    scenario_id: int = Field(index=True, foreign_key="scenario.id")
    event_id: Optional[int] = None
    title: str
    status: IncidentStatus = IncidentStatus.OPEN
    started_at: datetime = Field(default_factory=utcnow)  # attack injected
    detected_at: Optional[datetime] = None
    triaged_at: Optional[datetime] = None
    contained_at: Optional[datetime] = None
    recovered_at: Optional[datetime] = None
    assigned_to: str = ""
    score: Optional[int] = None


class Setting(SQLModel, table=True):
    """Simple key/value store for global exercise state (kill switch, etc.)."""

    key: str = Field(primary_key=True)
    value: str = ""


class Defense(SQLModel, table=True):
    """A countermeasure applied by the blue team (also serves as the blocklist)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=utcnow, index=True)
    scenario_id: Optional[int] = Field(default=None, index=True)
    incident_id: Optional[int] = None
    attack_type: str = ""
    action: str = Field(index=True)     # e.g. "block_ip"
    target: str = ""                    # ip / domain / node
    effective: bool = True
    actor: str = ""


class WebSecAttempt(SQLModel, table=True):
    """An exploit attempt against the MOD-02 Web Security Lab."""

    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=utcnow, index=True)
    vuln_id: str = Field(index=True)
    payload: str = ""
    success: bool = False        # did the attack work (i.e. was the vuln unpatched)?
    src_ip: str = ""
    detail: str = ""
