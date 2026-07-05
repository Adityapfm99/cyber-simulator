"""§2 Event Injection + §3 attack scenarios.

Injecting an event:
  1. validates it against §4 guardrails (allowed dummy type, no secrets),
  2. writes attack logs into the SIEM stream,
  3. marks the target node compromised (or OT fault),
  4. opens an Incident so the response clock starts.

Scheduled events carry a ``scheduled_at``; a background ticker injects them when
their time arrives.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlmodel import Session, select

from . import audit, guardrails, scoring, soc
from .models import Event, LogEntry, Node, NodeStatus, Scenario, ScenarioStatus, utcnow

# Attacker's dummy source address (clearly not a real host).
ATTACKER_IP = "10.66.66.66"


def create_event(
    session: Session,
    actor: str,
    scenario_id: int,
    event_type: str,
    title: str,
    target_node: str = "",
    payload: dict | None = None,
    scheduled_at: datetime | None = None,
) -> Event:
    guardrails.validate_event_type(event_type)
    payload = payload or {}
    guardrails.scan_for_secrets(json.dumps(payload))
    for v in payload.values():
        if isinstance(v, str):
            guardrails.scan_for_secrets(v)

    event = Event(
        scenario_id=scenario_id,
        type=event_type,
        title=title,
        target_node=target_node,
        payload=json.dumps(payload),
        scheduled_at=scheduled_at,
        injected_by=actor,
        status="pending",
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    audit.record(session, actor, "event.create", str(event.id),
                 {"type": event_type, "scheduled": bool(scheduled_at)})
    return event


def inject(session: Session, actor: str, event_id: int) -> dict:
    """Execute an event now. Returns the incident + generated logs."""
    guardrails.require_not_killed(session)
    event = session.get(Event, event_id)
    if event is None:
        raise guardrails.GuardrailViolation("Event not found")
    if event.status == "injected":
        raise guardrails.GuardrailViolation("Event already injected")

    scenario = session.get(Scenario, event.scenario_id)
    if scenario is None or scenario.status != ScenarioStatus.RUNNING:
        raise guardrails.GuardrailViolation("Scenario is not running")

    # Persistent defense: if the attacker IP is on the blocklist, the NGFW stops
    # the attack before it lands (no compromise, no incident).
    from . import defense
    if defense.is_ip_blocked(session, ATTACKER_IP, event.scenario_id):
        blocked_log = LogEntry(
            scenario_id=event.scenario_id, source="firewall", severity="notice",
            src_ip=ATTACKER_IP, dst_ip="",
            message=f"BLOCK {event.type} from {ATTACKER_IP} — source on NGFW blocklist "
                    f"(attack prevented)",
        )
        session.add(blocked_log)
        event.status = "injected"
        event.injected_at = utcnow()
        event.injected_by = actor
        session.add(event)
        session.commit()
        audit.record(session, actor, "event.inject.blocked", str(event.id),
                     {"type": event.type, "reason": "attacker IP blocklisted"})
        return {"event": event, "incident": None, "blocked": True,
                "logs": [{"source": "firewall", "severity": "notice",
                          "message": blocked_log.message, "src_ip": ATTACKER_IP,
                          "dst_ip": ""}]}

    # Resolve target node.
    target = None
    if event.target_node:
        target = session.exec(
            select(Node).where(
                Node.scenario_id == event.scenario_id, Node.name == event.target_node
            )
        ).first()

    target_ip = target.ip if target else ""

    # Generate attack logs into the SIEM.
    logs = soc.generate_attack(
        session, event.scenario_id, event.type, target_ip, ATTACKER_IP, event.id
    )
    for lg in logs:
        session.add(lg)

    # Update node state.
    if target:
        if event.type == "ot_fault":
            target.status = NodeStatus.COMPROMISED
        elif event.type == "ransomware":
            target.status = NodeStatus.COMPROMISED
        else:
            target.status = NodeStatus.COMPROMISED
        session.add(target)

    event.status = "injected"
    event.injected_at = utcnow()
    event.injected_by = actor
    session.add(event)
    session.commit()

    incident = scoring.open_incident(
        session, event.scenario_id, event.id, f"{event.type}: {event.title}"
    )

    audit.record(session, actor, "event.inject", str(event.id),
                 {"type": event.type, "target": event.target_node,
                  "incident": incident.id})

    session.refresh(event)
    return {
        "event": event,
        "incident": incident,
        "logs": [
            {"source": l.source, "severity": l.severity, "message": l.message,
             "src_ip": l.src_ip, "dst_ip": l.dst_ip}
            for l in logs
        ],
    }


def due_scheduled(session: Session) -> list[Event]:
    """Return pending scheduled events whose time has arrived."""
    now = utcnow()
    events = session.exec(
        select(Event).where(Event.status == "pending")
    ).all()
    due = []
    for e in events:
        if e.scheduled_at is not None:
            sched = e.scheduled_at
            if sched.tzinfo is None:
                sched = sched.replace(tzinfo=timezone.utc)
            if sched <= now:
                due.append(e)
    return due
