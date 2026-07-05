"""§3 C2 Resilience & Supply-Chain — Commander leadership dashboard.

Produces the high-level operational picture a Commander sees:
  * facility status derived from OT/ICS node health,
  * C2 link health,
  * third-party vendor integrity (expired certs / hash mismatch),
  * an incident summary.

The spec's defining requirement is that under **simulated jamming** the leadership
picture becomes *delayed and conflicting* — decision-makers must cope with an
unreliable feed. So when a ``c2_jamming`` event is active we deliberately return a
stale sync time and two disagreeing situation reports instead of one clean number.
"""
from __future__ import annotations

from sqlmodel import Session, select

from .models import Event, Incident, IncidentStatus, Node, Scenario, as_utc, utcnow

_OT_ROLES = {"hmi", "plc-power", "plc-hvac", "historian"}


def _active_events(session: Session, scenario_id: int, event_type: str) -> list[Event]:
    """Injected events of a type whose incident is not yet recovered."""
    events = session.exec(
        select(Event).where(
            Event.scenario_id == scenario_id,
            Event.type == event_type,
            Event.status == "injected",
        )
    ).all()
    active = []
    for ev in events:
        inc = session.exec(
            select(Incident).where(Incident.event_id == ev.id)
        ).first()
        if inc is None or inc.status != IncidentStatus.RECOVERED:
            active.append(ev)
    return active


def build_dashboard(session: Session, scenario_id: int) -> dict:
    scenario = session.get(Scenario, scenario_id)
    if scenario is None:
        raise ValueError("Scenario not found")

    nodes = session.exec(select(Node).where(Node.scenario_id == scenario_id)).all()
    incidents = session.exec(
        select(Incident).where(Incident.scenario_id == scenario_id)
    ).all()

    # --- Facilities (OT/ICS) -------------------------------------------------
    facilities = []
    facility_state = "operational"
    for n in nodes:
        if n.kind == "ot" or n.role in _OT_ROLES:
            fstat = {
                "up": "operational", "compromised": "critical",
                "quarantined": "degraded", "halted": "offline",
                "destroyed": "offline",
            }.get(n.status, "unknown")
            facilities.append({"name": n.name, "role": n.role, "state": fstat})
            if fstat == "critical":
                facility_state = "critical"
            elif fstat in ("degraded", "offline") and facility_state != "critical":
                facility_state = "degraded"

    # --- C2 link + vendor integrity -----------------------------------------
    jamming = _active_events(session, scenario_id, "c2_jamming")
    vendor_events = _active_events(session, scenario_id, "supply_chain_anomaly")
    degraded = bool(jamming)

    vendor = {"status": "ok", "issues": []}
    if vendor_events:
        vendor = {
            "status": "anomaly",
            "issues": [
                "Vendor gateway presented an expired TLS certificate.",
                "Artifact hash mismatch: expected != actual on last vendor push.",
            ],
        }

    open_incidents = [i for i in incidents if i.status != IncidentStatus.RECOVERED]

    # --- Situation reports ---------------------------------------------------
    # Nominal: one authoritative figure. Under jamming: conflicting + stale.
    if degraded:
        primary = len(open_incidents)
        # A jammed backup feed disagrees (dropped/duplicated telemetry).
        backup = max(0, primary + (2 if primary else 1) - 1)
        reports = [
            {"source": "Primary C2 feed", "open_incidents": primary,
             "confidence": "low", "note": "link jammed — data may be delayed"},
            {"source": "Backup relay", "open_incidents": backup,
             "confidence": "low", "note": "partial telemetry, unreconciled"},
        ]
        last_sync = "STALE — link degraded, last reliable sync unknown"
    else:
        reports = [
            {"source": "Primary C2 feed", "open_incidents": len(open_incidents),
             "confidence": "high", "note": "link nominal"},
        ]
        last_sync = as_utc(utcnow()).isoformat()

    return {
        "scenario": {"id": scenario.id, "name": scenario.name, "status": scenario.status},
        "c2_link": {
            "status": "degraded" if degraded else "nominal",
            "jamming_active": degraded,
            "note": "Simulated jamming — situational data is delayed and conflicting."
            if degraded else "Command-and-control link nominal.",
        },
        "facility_state": facility_state,
        "facilities": facilities,
        "vendor_integrity": vendor,
        "incident_summary": {
            "total": len(incidents),
            "open": len(open_incidents),
            "recovered": len(incidents) - len(open_incidents),
        },
        "situation_reports": reports,
        "last_sync": last_sync,
        "data_reliable": not degraded,
    }
