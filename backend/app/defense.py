"""Per-attack countermeasures (defensive actions).

Each attack type has a set of **effective** countermeasures. The analyst must pick
the right one — applying an effective action neutralizes the attack (advances the
incident to contained/recovered and updates node state), while an irrelevant
action is recorded as "not effective" (teaching feedback).

Some actions leave **persistent** state: ``block_ip`` / ``block_domain`` add to a
blocklist so a follow-on attack from the same source is prevented in
``events.inject``.
"""
from __future__ import annotations

from sqlmodel import Session, select

from . import audit, scoring
from .models import Defense, Event, Incident, IncidentStatus, LogEntry, Node, NodeStatus, Scenario, ScenarioStatus, utcnow

ATTACKER_IP = "10.66.66.66"

# Catalog of defensive actions. needs = what the target field means.
ACTIONS = {
    "block_ip": {"label": "Block source IP (NGFW)", "needs": "ip"},
    "harden_node": {"label": "Harden / close unused ports", "needs": "node"},
    "block_domain": {"label": "Block malicious domain (DNS/Proxy)", "needs": "domain"},
    "reset_credentials": {"label": "Reset credentials / lock account", "needs": "account"},
    "isolate_host": {"label": "Isolate / quarantine host", "needs": "node"},
    "restore_backup": {"label": "Restore from backup", "needs": "node"},
    "revoke_vendor": {"label": "Quarantine vendor / revoke cert", "needs": "node"},
    "ot_safe_mode": {"label": "PLC failover / safe mode", "needs": "node"},
    "switch_comms": {"label": "Switch to backup comms link", "needs": "node"},
    "dlp_block": {"label": "Enable DLP / block exfil channel", "needs": "domain"},
}

# Which countermeasures are effective for each attack, in recommended order.
ATTACK_DEFENSES = {
    "portscan": ["block_ip", "harden_node"],
    "phishing": ["block_domain", "reset_credentials"],
    "supply_chain_anomaly": ["revoke_vendor"],
    "bruteforce": ["reset_credentials", "block_ip"],
    "lateral_move": ["isolate_host", "block_ip"],
    "ransomware": ["isolate_host", "block_domain", "restore_backup"],
    "data_exfil": ["block_ip", "block_domain", "dlp_block"],
    "dns_tunnel": ["block_domain", "dlp_block"],
    "ot_fault": ["isolate_host", "ot_safe_mode"],
    "c2_jamming": ["switch_comms"],
}

# Characteristic malicious domain per attack (for block_domain / dlp_block).
_DOMAINS = {
    "phishing": "vendor-portal.lab", "ransomware": "drop.lab",
    "data_exfil": "exfil.lab", "dns_tunnel": "tunnel.lab",
}
# Actions that fully recover (rather than just contain) the incident.
_RECOVERY = {"restore_backup"}


class DefenseError(Exception):
    """Invalid countermeasure request (HTTP 422)."""


def _default_target(attack_type: str, action: str, target_node: str) -> str:
    need = ACTIONS[action]["needs"]
    if need == "ip":
        return ATTACKER_IP
    if need == "domain":
        return _DOMAINS.get(attack_type, "malicious.lab")
    if need == "account":
        return "blue-lead"
    return target_node  # node


def is_ip_blocked(session: Session, ip: str, scenario_id: int | None = None) -> bool:
    q = select(Defense).where(Defense.action == "block_ip", Defense.target == ip,
                              Defense.effective == True)  # noqa: E712
    if scenario_id is not None:
        q = q.where(Defense.scenario_id == scenario_id)
    return session.exec(q).first() is not None


def blocklist(session: Session, scenario_id: int | None = None) -> dict:
    q = select(Defense).where(Defense.effective == True)  # noqa: E712
    if scenario_id is not None:
        q = q.where(Defense.scenario_id == scenario_id)
    rows = session.exec(q).all()
    return {
        "ips": sorted({d.target for d in rows if d.action == "block_ip"}),
        "domains": sorted({d.target for d in rows if d.action in ("block_domain", "dlp_block")}),
    }


def available_for(session: Session, incident: Incident) -> dict:
    """Countermeasures relevant to an incident + which are already applied."""
    ev = session.get(Event, incident.event_id) if incident.event_id else None
    atype = ev.type if ev else ""
    applied = {
        d.action for d in session.exec(
            select(Defense).where(Defense.incident_id == incident.id)
        ).all()
    }
    actions = []
    for aid in ATTACK_DEFENSES.get(atype, []):
        actions.append({
            "id": aid, "label": ACTIONS[aid]["label"],
            "applied": aid in applied,
            "target": _default_target(atype, aid, ev.target_node if ev else ""),
        })
    return {"attack_type": atype, "countermeasures": actions}


def apply(session: Session, actor: str, incident_id: int, action: str,
          target: str = "") -> dict:
    if action not in ACTIONS:
        raise DefenseError(f"Unknown action {action!r}")
    incident = session.get(Incident, incident_id)
    if incident is None:
        raise DefenseError("Incident not found")
    ev = session.get(Event, incident.event_id) if incident.event_id else None
    atype = ev.type if ev else ""
    effective_actions = ATTACK_DEFENSES.get(atype, [])
    effective = action in effective_actions
    tgt = target or _default_target(atype, action, ev.target_node if ev else "")

    # Record the countermeasure (also feeds the blocklist).
    session.add(Defense(
        scenario_id=incident.scenario_id, incident_id=incident_id, attack_type=atype,
        action=action, target=tgt, effective=effective, actor=actor,
    ))
    session.commit()
    audit.record(session, actor, "defense.apply", str(incident_id),
                 {"action": action, "target": tgt, "effective": effective})

    # SOC feed line.
    _soc(session, incident.scenario_id,
         f"countermeasure {action} target={tgt} -> "
         f"{'ATTACK NEUTRALIZED' if effective else 'no effect (wrong countermeasure)'}",
         "notice" if effective else "info")

    if not effective:
        return {"effective": False,
                "message": f"'{ACTIONS[action]['label']}' tidak efektif untuk serangan "
                           f"{atype}. Coba: {[ACTIONS[a]['label'] for a in effective_actions]}",
                "incident": _inc_view(incident)}

    # Effective: apply node/state effect + advance the incident.
    node = None
    if ev and ev.target_node:
        node = session.exec(
            select(Node).where(Node.scenario_id == incident.scenario_id,
                               Node.name == ev.target_node)
        ).first()
    if node is not None:
        if action in ("isolate_host", "revoke_vendor"):
            node.status = NodeStatus.QUARANTINED
        elif action in ("restore_backup", "ot_safe_mode"):
            node.status = NodeStatus.UP
        session.add(node)
        session.commit()

    scoring.ensure_contained(session, actor, incident_id)
    if action in _RECOVERY or _all_effective_applied(session, incident_id, effective_actions):
        scoring.advance(session, actor, incident_id, "recover")
        if node is not None:
            node.status = NodeStatus.UP
            session.add(node)
            session.commit()

    session.refresh(incident)
    return {"effective": True,
            "message": f"'{ACTIONS[action]['label']}' berhasil — serangan {atype} dinetralkan.",
            "incident": _inc_view(incident)}


def _all_effective_applied(session, incident_id, effective_actions) -> bool:
    applied = {d.action for d in session.exec(
        select(Defense).where(Defense.incident_id == incident_id,
                              Defense.effective == True)  # noqa: E712
    ).all()}
    return set(effective_actions).issubset(applied)


def _inc_view(inc: Incident) -> dict:
    return {"id": inc.id, "status": inc.status, "score": inc.score,
            "metrics": scoring.metrics(inc)}


def _soc(session: Session, scenario_id: int, message: str, severity: str) -> None:
    session.add(LogEntry(scenario_id=scenario_id, source="waf", severity=severity,
                         message=message, dst_ip="10.10.0.1"))
    session.commit()
