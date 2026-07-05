"""§2 Scoring Engine.

Each injected attack opens an ``Incident`` whose clock starts at injection. As the
SOC analyst progresses the response, we stamp the four canonical times:

  TTD  Time to Detect   (started -> detected)
  TTT  Time to Triage   (started -> triaged)
  TTC  Time to Contain  (started -> contained)
  TTR  Time to Recover  (started -> recovered)

A score (0-100) rewards beating the target thresholds from config.
"""
from __future__ import annotations

from sqlmodel import Session, select

from . import audit, guardrails
from .config import TARGET_TTC, TARGET_TTD, TARGET_TTR, TARGET_TTT
from .models import Incident, IncidentStatus, as_utc, utcnow

# Ordered lifecycle transitions the analyst can perform.
_TRANSITIONS = {
    "detect": ("detected_at", IncidentStatus.DETECTED),
    "triage": ("triaged_at", IncidentStatus.TRIAGED),
    "contain": ("contained_at", IncidentStatus.CONTAINED),
    "recover": ("recovered_at", IncidentStatus.RECOVERED),
}


def _elapsed(incident: Incident, field: str) -> float | None:
    ts = as_utc(getattr(incident, field))
    if ts is None:
        return None
    start = as_utc(incident.started_at)
    return (ts - start).total_seconds()


def metrics(incident: Incident) -> dict:
    return {
        "TTD": _elapsed(incident, "detected_at"),
        "TTT": _elapsed(incident, "triaged_at"),
        "TTC": _elapsed(incident, "contained_at"),
        "TTR": _elapsed(incident, "recovered_at"),
    }


def _score(m: dict) -> int:
    """25 points per phase, scaled down when the target time is exceeded."""
    targets = {"TTD": TARGET_TTD, "TTT": TARGET_TTT, "TTC": TARGET_TTC, "TTR": TARGET_TTR}
    total = 0.0
    for phase, target in targets.items():
        val = m.get(phase)
        if val is None:
            continue
        # Full 25 if at/under target; decays toward 0 at 4x target.
        ratio = val / target if target else 1.0
        phase_score = 25.0 if ratio <= 1 else max(0.0, 25.0 * (1 - (ratio - 1) / 3))
        total += phase_score
    return round(total)


def advance(session: Session, actor: str, incident_id: int, action: str) -> Incident:
    if action not in _TRANSITIONS:
        raise guardrails.GuardrailViolation(f"Unknown response action: {action!r}")
    incident = session.get(Incident, incident_id)
    if incident is None:
        raise guardrails.GuardrailViolation("Incident not found")

    field, new_status = _TRANSITIONS[action]
    if getattr(incident, field) is None:
        setattr(incident, field, utcnow())
    incident.status = new_status
    if not incident.assigned_to:
        incident.assigned_to = actor
    incident.score = _score(metrics(incident))
    session.add(incident)
    session.commit()
    session.refresh(incident)
    audit.record(session, actor, f"incident.{action}", str(incident_id),
                 {"status": new_status, "score": incident.score})
    return incident


def open_incident(session: Session, scenario_id: int, event_id: int, title: str) -> Incident:
    incident = Incident(
        scenario_id=scenario_id, event_id=event_id, title=title,
        status=IncidentStatus.OPEN,
    )
    session.add(incident)
    session.commit()
    session.refresh(incident)
    return incident


def scenario_scoreboard(session: Session, scenario_id: int) -> dict:
    incidents = session.exec(
        select(Incident).where(Incident.scenario_id == scenario_id)
    ).all()
    rows = []
    total = 0
    for inc in incidents:
        m = metrics(inc)
        rows.append({
            "id": inc.id, "title": inc.title, "status": inc.status,
            "assigned_to": inc.assigned_to, "score": inc.score, "metrics": m,
        })
        total += inc.score or 0
    avg = round(total / len(incidents)) if incidents else 0
    return {"incidents": rows, "average_score": avg, "count": len(incidents)}
