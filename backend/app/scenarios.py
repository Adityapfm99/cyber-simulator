"""§2 Scenario Engine.

Loads Infrastructure-as-Code style templates and "deploys" / "destroys" a
simulated lab: nodes (VMs/containers/OT), topology edges, and the notional
provisioning that in a real deployment would call out to a hypervisor/IaC layer.

Because this is a training simulator, deploy/destroy operate on database records
rather than real hypervisors — but the same guardrails (isolation, dummy data)
are enforced as if they were real.
"""
from __future__ import annotations

from datetime import datetime, timezone

import yaml
from sqlmodel import Session, select

from . import audit, guardrails
from .config import SCENARIO_TEMPLATE_DIR
from .models import (
    Edge,
    Node,
    NodeStatus,
    Scenario,
    ScenarioStatus,
    utcnow,
)


def list_templates() -> list[dict]:
    templates = []
    for path in sorted(SCENARIO_TEMPLATE_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text())
        templates.append({
            "id": path.stem,
            "name": data.get("name", path.stem),
            "description": data.get("description", "").strip(),
            "node_count": len(data.get("nodes", [])),
        })
    return templates


def _load_template(template_id: str) -> dict:
    path = SCENARIO_TEMPLATE_DIR / f"{template_id}.yaml"
    if not path.exists():
        raise guardrails.GuardrailViolation(f"Unknown template: {template_id!r}")
    return yaml.safe_load(path.read_text())


def create_scenario(
    session: Session, actor: str, template_id: str, name: str | None = None
) -> Scenario:
    data = _load_template(template_id)
    scenario = Scenario(
        name=name or data.get("name", template_id),
        template=template_id,
        description=data.get("description", "").strip(),
        status=ScenarioStatus.DRAFT,
        created_by=actor,
    )
    session.add(scenario)
    session.commit()
    session.refresh(scenario)
    audit.record(session, actor, "scenario.create", str(scenario.id),
                 {"template": template_id, "name": scenario.name})
    return scenario


def deploy(session: Session, actor: str, scenario_id: int) -> Scenario:
    """IaC-style deploy: instantiate topology, enforcing §4 guardrails."""
    guardrails.require_not_killed(session)
    scenario = session.get(Scenario, scenario_id)
    if scenario is None:
        raise guardrails.GuardrailViolation("Scenario not found")
    if scenario.status in (ScenarioStatus.RUNNING, ScenarioStatus.DEPLOYING):
        return scenario

    data = _load_template(scenario.template)
    isolation = guardrails.is_isolation_enforced(session)

    # Wipe any prior topology (re-deploy).
    for old in session.exec(select(Node).where(Node.scenario_id == scenario_id)).all():
        session.delete(old)
    for old in session.exec(select(Edge).where(Edge.scenario_id == scenario_id)).all():
        session.delete(old)

    for n in data.get("nodes", []):
        ip = n.get("ip", "")
        if isolation:
            guardrails.validate_ip(ip)          # reject public/routable IPs
        session.add(Node(
            scenario_id=scenario_id,
            name=n["name"],
            kind=n.get("kind", "vm"),
            role=n.get("role", ""),
            ip=ip,
            status=NodeStatus.UP,
        ))
    for e in data.get("edges", []):
        src, dst = e
        session.add(Edge(scenario_id=scenario_id, src=src, dst=dst))

    scenario.status = ScenarioStatus.RUNNING
    scenario.deployed_at = utcnow()
    session.add(scenario)
    session.commit()
    session.refresh(scenario)
    audit.record(session, actor, "scenario.deploy", str(scenario_id),
                 {"nodes": len(data.get("nodes", [])), "isolation": isolation})
    return scenario


def destroy(session: Session, actor: str, scenario_id: int) -> Scenario:
    scenario = session.get(Scenario, scenario_id)
    if scenario is None:
        raise guardrails.GuardrailViolation("Scenario not found")
    for node in session.exec(select(Node).where(Node.scenario_id == scenario_id)).all():
        node.status = NodeStatus.DESTROYED
        session.add(node)
    scenario.status = ScenarioStatus.DESTROYED
    scenario.destroyed_at = utcnow()
    session.add(scenario)
    session.commit()
    session.refresh(scenario)
    audit.record(session, actor, "scenario.destroy", str(scenario_id))
    return scenario


def topology(session: Session, scenario_id: int) -> dict:
    nodes = session.exec(select(Node).where(Node.scenario_id == scenario_id)).all()
    edges = session.exec(select(Edge).where(Edge.scenario_id == scenario_id)).all()
    return {
        "nodes": [
            {"id": n.name, "kind": n.kind, "role": n.role, "ip": n.ip,
             "status": n.status}
            for n in nodes
        ],
        "edges": [{"src": e.src, "dst": e.dst} for e in edges],
    }


def baseline_lps(template_id: str) -> int:
    data = _load_template(template_id)
    return int(data.get("traffic", {}).get("baseline_lps", 4))


# Containment actions an analyst performs on a node, and the status they set.
_NODE_ACTIONS = {
    "quarantine": NodeStatus.QUARANTINED,   # isolate host from the network
    "isolate": NodeStatus.QUARANTINED,       # alias
    "restore": NodeStatus.UP,                # bring a clean/recovered host back
}


def node_action(
    session: Session, actor: str, scenario_id: int, node_name: str, action: str
) -> dict:
    """Apply a containment/recovery action to a node.

    Quarantining the node targeted by an open incident advances that incident to
    'contained'; restoring it advances to 'recovered'. This makes the topology
    controls drive the scoring model the way a real response would.
    """
    from . import scoring  # local import avoids a circular dependency

    guardrails.require_not_killed(session)
    if action not in _NODE_ACTIONS:
        raise guardrails.GuardrailViolation(
            f"Unknown node action {action!r}. Allowed: {sorted(_NODE_ACTIONS)}"
        )
    node = session.exec(
        select(Node).where(Node.scenario_id == scenario_id, Node.name == node_name)
    ).first()
    if node is None:
        raise guardrails.GuardrailViolation("Node not found")

    node.status = _NODE_ACTIONS[action]
    session.add(node)
    session.commit()
    audit.record(session, actor, f"node.{action}", node_name,
                 {"scenario": scenario_id, "status": node.status})

    # Drive linked incidents (matched by the injecting event's target node).
    advanced = []
    from .models import Event, Incident, IncidentStatus
    incidents = session.exec(
        select(Incident).where(Incident.scenario_id == scenario_id)
    ).all()
    for inc in incidents:
        if inc.status == IncidentStatus.RECOVERED or inc.event_id is None:
            continue
        ev = session.get(Event, inc.event_id)
        if ev is None or ev.target_node != node_name:
            continue
        if action in ("quarantine", "isolate") and inc.status != IncidentStatus.CONTAINED:
            scoring.advance(session, actor, inc.id, "contain")
            advanced.append({"incident": inc.id, "to": "contained"})
        elif action == "restore":
            scoring.advance(session, actor, inc.id, "recover")
            advanced.append({"incident": inc.id, "to": "recovered"})

    return {"node": node_name, "status": node.status, "incidents_advanced": advanced}
