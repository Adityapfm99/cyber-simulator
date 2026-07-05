"""HTTP + WebSocket API surface."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import (
    APIRouter, Depends, HTTPException, Request, Response, WebSocket,
    WebSocketDisconnect,
)
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlmodel import Session, select

from . import (
    aar, audit, c2, config, events, guardrails, ot, scenarios, scoring, soc,
    webseclab,
)
from .auth import authenticate, create_token, get_current_user, require_roles
from .database import get_session
from .guardrails import GuardrailViolation
from .models import Event, LogEntry, Role, Scenario, ScenarioStatus, User
from .realtime import hub

router = APIRouter()


def _guard(exc: GuardrailViolation) -> HTTPException:
    return HTTPException(status_code=422, detail=str(exc))


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
@router.post("/auth/login", tags=["auth"])
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
):
    user = authenticate(session, form.username, form.password)
    if not user:
        audit.record(session, form.username, "auth.login.fail")
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    audit.record(session, user.username, "auth.login.ok", details={"role": user.role})
    return {
        "access_token": create_token(user.username, user.role),
        "token_type": "bearer",
        "role": user.role,
        "username": user.username,
    }


@router.get("/auth/me", tags=["auth"])
def me(user: User = Depends(get_current_user)):
    return {"username": user.username, "role": user.role}


# --------------------------------------------------------------------------- #
# Scenarios (§2 Scenario Engine)
# --------------------------------------------------------------------------- #
class CreateScenario(BaseModel):
    template: str
    name: Optional[str] = None


@router.get("/scenarios/templates", tags=["scenarios"])
def templates(user: User = Depends(get_current_user)):
    return scenarios.list_templates()


@router.get("/scenarios", tags=["scenarios"])
def list_scenarios(
    user: User = Depends(get_current_user), session: Session = Depends(get_session)
):
    rows = session.exec(select(Scenario).order_by(Scenario.id.desc())).all()
    return rows


@router.post("/scenarios", tags=["scenarios"])
def create_scenario(
    body: CreateScenario,
    user: User = Depends(require_roles(Role.ADMIN, Role.DIRECTOR)),
    session: Session = Depends(get_session),
):
    try:
        return scenarios.create_scenario(session, user.username, body.template, body.name)
    except GuardrailViolation as exc:
        raise _guard(exc)


@router.get("/scenarios/{scenario_id}", tags=["scenarios"])
def get_scenario(
    scenario_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    sc = session.get(Scenario, scenario_id)
    if not sc:
        raise HTTPException(404, "Scenario not found")
    return sc


@router.post("/scenarios/{scenario_id}/deploy", tags=["scenarios"])
async def deploy_scenario(
    scenario_id: int,
    user: User = Depends(require_roles(Role.ADMIN, Role.DIRECTOR)),
    session: Session = Depends(get_session),
):
    try:
        sc = scenarios.deploy(session, user.username, scenario_id)
    except GuardrailViolation as exc:
        raise _guard(exc)
    await hub.publish(scenario_id, {"kind": "topology", "data": scenarios.topology(session, scenario_id)})
    await hub.publish(scenario_id, {"kind": "status", "data": {"status": sc.status}})
    return sc


@router.post("/scenarios/{scenario_id}/destroy", tags=["scenarios"])
async def destroy_scenario(
    scenario_id: int,
    user: User = Depends(require_roles(Role.ADMIN, Role.DIRECTOR)),
    session: Session = Depends(get_session),
):
    try:
        sc = scenarios.destroy(session, user.username, scenario_id)
    except GuardrailViolation as exc:
        raise _guard(exc)
    await hub.publish(scenario_id, {"kind": "status", "data": {"status": sc.status}})
    return sc


@router.get("/scenarios/{scenario_id}/topology", tags=["scenarios"])
def get_topology(
    scenario_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return scenarios.topology(session, scenario_id)


@router.post("/scenarios/{scenario_id}/nodes/{node_name}/action", tags=["scenarios"])
async def node_action(
    scenario_id: int,
    node_name: str,
    action: str,
    user: User = Depends(require_roles(Role.ADMIN, Role.ANALYST)),
    session: Session = Depends(get_session),
):
    try:
        result = scenarios.node_action(session, user.username, scenario_id, node_name, action)
    except GuardrailViolation as exc:
        raise _guard(exc)
    await hub.publish(scenario_id, {"kind": "topology",
                                    "data": scenarios.topology(session, scenario_id)})
    for adv in result["incidents_advanced"]:
        await hub.publish(scenario_id, {"kind": "incident", "data": adv})
    return result


# --------------------------------------------------------------------------- #
# Commander C2 dashboard (§3 C2 Resilience & Supply Chain)
# --------------------------------------------------------------------------- #
@router.get("/scenarios/{scenario_id}/c2", tags=["c2"])
def c2_dashboard(
    scenario_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    try:
        return c2.build_dashboard(session, scenario_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))


# --------------------------------------------------------------------------- #
# MOD-03 OT/ICS Digital Twin — HMI telemetry
# --------------------------------------------------------------------------- #
@router.get("/scenarios/{scenario_id}/ot", tags=["ot"])
def ot_telemetry(
    scenario_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    try:
        return ot.telemetry(session, scenario_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))


# --------------------------------------------------------------------------- #
# Events (§2 Event Injection / §3 attacks)
# --------------------------------------------------------------------------- #
class CreateEvent(BaseModel):
    type: str
    title: str
    target_node: str = ""
    payload: dict = {}
    scheduled_at: Optional[datetime] = None


@router.get("/events/catalog", tags=["events"])
def event_catalog(user: User = Depends(get_current_user)):
    return sorted(guardrails.ALLOWED_EVENT_TYPES)


@router.get("/scenarios/{scenario_id}/events", tags=["events"])
def list_events(
    scenario_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return session.exec(
        select(Event).where(Event.scenario_id == scenario_id).order_by(Event.id.desc())
    ).all()


@router.post("/scenarios/{scenario_id}/events", tags=["events"])
def create_event(
    scenario_id: int,
    body: CreateEvent,
    user: User = Depends(require_roles(Role.ADMIN, Role.DIRECTOR)),
    session: Session = Depends(get_session),
):
    try:
        return events.create_event(
            session, user.username, scenario_id, body.type, body.title,
            body.target_node, body.payload, body.scheduled_at,
        )
    except GuardrailViolation as exc:
        raise _guard(exc)


@router.post("/events/{event_id}/inject", tags=["events"])
async def inject_event(
    event_id: int,
    user: User = Depends(require_roles(Role.ADMIN, Role.DIRECTOR)),
    session: Session = Depends(get_session),
):
    try:
        result = events.inject(session, user.username, event_id)
    except GuardrailViolation as exc:
        raise _guard(exc)
    sid = result["event"].scenario_id
    for lg in result["logs"]:
        await hub.publish(sid, {"kind": "log", "data": lg})
    await hub.publish(sid, {"kind": "event", "data": {
        "title": result["event"].title, "type": result["event"].type,
        "incident_id": result["incident"].id,
    }})
    await hub.publish(sid, {"kind": "topology", "data": scenarios.topology(session, sid)})
    return {
        "event_id": result["event"].id,
        "incident_id": result["incident"].id,
        "logs": result["logs"],
    }


# --------------------------------------------------------------------------- #
# SOC logs (§3 SOC Simulator)
# --------------------------------------------------------------------------- #
@router.get("/scenarios/{scenario_id}/logs", tags=["soc"])
def recent_logs(
    scenario_id: int,
    limit: int = 100,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    # In serverless mode there is no background ticker, so lazily materialize
    # baseline traffic and fire any due scheduled events on each poll.
    if not config.RUN_BACKGROUND and not guardrails.is_kill_switch_engaged(session):
        sc = session.get(Scenario, scenario_id)
        if sc and sc.status == ScenarioStatus.RUNNING:
            soc.lazy_fill(session, scenario_id)
            for ev in events.due_scheduled(session):
                try:
                    events.inject(session, "scheduler", ev.id)
                except Exception:
                    pass
    rows = session.exec(
        select(LogEntry).where(LogEntry.scenario_id == scenario_id)
        .order_by(LogEntry.id.desc()).limit(limit)
    ).all()
    return list(reversed(rows))


# --------------------------------------------------------------------------- #
# Scoring + incidents (§2)
# --------------------------------------------------------------------------- #
@router.get("/scenarios/{scenario_id}/scoreboard", tags=["scoring"])
def scoreboard(
    scenario_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return scoring.scenario_scoreboard(session, scenario_id)


@router.post("/incidents/{incident_id}/advance", tags=["scoring"])
async def advance_incident(
    incident_id: int,
    action: str,
    user: User = Depends(require_roles(Role.ADMIN, Role.ANALYST)),
    session: Session = Depends(get_session),
):
    try:
        inc = scoring.advance(session, user.username, incident_id, action)
    except GuardrailViolation as exc:
        raise _guard(exc)
    await hub.publish(inc.scenario_id, {"kind": "incident", "data": {
        "id": inc.id, "status": inc.status, "score": inc.score,
    }})
    return {"id": inc.id, "status": inc.status, "score": inc.score,
            "metrics": scoring.metrics(inc)}


# --------------------------------------------------------------------------- #
# AAR (§2 After-Action Review)
# --------------------------------------------------------------------------- #
@router.get("/scenarios/{scenario_id}/aar", tags=["aar"])
def aar_json(
    scenario_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    try:
        return aar.build_report(session, scenario_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.get("/scenarios/{scenario_id}/aar.pdf", tags=["aar"])
def aar_pdf(
    scenario_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    data, media = aar.render_pdf(session, scenario_id)
    ext = "pdf" if media == "application/pdf" else "html"
    return Response(content=data, media_type=media, headers={
        "Content-Disposition": f'attachment; filename="aar-scenario-{scenario_id}.{ext}"'
    })


# --------------------------------------------------------------------------- #
# MOD-02 Web Security Lab (§3) — deliberately-vulnerable training app (sandboxed)
# --------------------------------------------------------------------------- #
class LoginBody(BaseModel):
    username: str = ""
    password: str = ""


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else ""


def _websec(exc: webseclab.WebSecError) -> HTTPException:
    return HTTPException(status_code=403, detail=str(exc))


@router.get("/lab/websec/registry", tags=["webseclab"])
def websec_registry(
    user: User = Depends(get_current_user), session: Session = Depends(get_session)
):
    return webseclab.registry(session)


@router.get("/lab/websec/attempts", tags=["webseclab"])
def websec_attempts(
    limit: int = 50,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return webseclab.recent_attempts(session, limit)


@router.post("/lab/websec/patch", tags=["webseclab"])
def websec_patch(
    vuln: str,
    patched: bool,
    user: User = Depends(require_roles(Role.ADMIN, Role.ANALYST)),
    session: Session = Depends(get_session),
):
    try:
        webseclab.set_patched(session, user.username, vuln, patched)
    except webseclab.WebSecError as exc:
        raise _websec(exc)
    return webseclab.registry(session)


@router.post("/lab/websec/login", tags=["webseclab"])
def websec_login(
    body: LoginBody, request: Request,
    user: User = Depends(get_current_user), session: Session = Depends(get_session),
):
    return webseclab.login(session, body.username, body.password, _client_ip(request))


@router.get("/lab/websec/search", tags=["webseclab"])
def websec_search(
    q: str, request: Request,
    user: User = Depends(get_current_user), session: Session = Depends(get_session),
):
    return webseclab.search(session, q, _client_ip(request))


@router.get("/lab/websec/invoice/{invoice_id}", tags=["webseclab"])
def websec_invoice(
    invoice_id: int, request: Request, as_user: str = "",
    user: User = Depends(get_current_user), session: Session = Depends(get_session),
):
    try:
        return webseclab.invoice(session, invoice_id, as_user, _client_ip(request))
    except webseclab.WebSecError as exc:
        raise _websec(exc)


@router.get("/lab/websec/ping", tags=["webseclab"])
def websec_ping(
    host: str, request: Request,
    user: User = Depends(get_current_user), session: Session = Depends(get_session),
):
    try:
        return webseclab.ping(session, host, _client_ip(request))
    except webseclab.WebSecError as exc:
        raise _websec(exc)


@router.get("/lab/websec/debug", tags=["webseclab"])
def websec_debug(
    request: Request,
    user: User = Depends(get_current_user), session: Session = Depends(get_session),
):
    try:
        return webseclab.debug(session, _client_ip(request))
    except webseclab.WebSecError as exc:
        raise _websec(exc)


# --------------------------------------------------------------------------- #
# Admin + guardrails (§4)
# --------------------------------------------------------------------------- #
class FlagBody(BaseModel):
    value: bool


@router.get("/admin/guardrails", tags=["admin"])
def guardrail_status(
    user: User = Depends(get_current_user), session: Session = Depends(get_session)
):
    return {
        "kill_switch": guardrails.is_kill_switch_engaged(session),
        "isolation_enforced": guardrails.is_isolation_enforced(session),
        "allowed_event_types": sorted(guardrails.ALLOWED_EVENT_TYPES),
        "dummy_identities": sorted(guardrails.DUMMY_IDENTITY_ALLOWLIST),
    }


@router.post("/admin/kill-switch", tags=["admin"])
async def kill_switch(
    body: FlagBody,
    user: User = Depends(require_roles(Role.ADMIN, Role.DIRECTOR)),
    session: Session = Depends(get_session),
):
    guardrails.set_kill_switch(session, body.value)
    audit.record(session, user.username, "guardrail.kill_switch",
                 details={"engaged": body.value})
    # Halt every running scenario's nodes when engaged.
    if body.value:
        from .models import Node, NodeStatus, ScenarioStatus
        running = session.exec(
            select(Scenario).where(Scenario.status == ScenarioStatus.RUNNING)
        ).all()
        for sc in running:
            for node in session.exec(select(Node).where(Node.scenario_id == sc.id)).all():
                node.status = NodeStatus.HALTED
                session.add(node)
            sc.status = ScenarioStatus.HALTED
            session.add(sc)
        session.commit()
        for sc in running:
            await hub.publish(sc.id, {"kind": "killswitch", "data": {"engaged": True}})
            await hub.publish(sc.id, {"kind": "topology",
                                      "data": scenarios.topology(session, sc.id)})
    return {"kill_switch": body.value}


@router.post("/admin/isolation", tags=["admin"])
def set_isolation(
    body: FlagBody,
    user: User = Depends(require_roles(Role.ADMIN)),
    session: Session = Depends(get_session),
):
    guardrails.set_isolation(session, body.value)
    audit.record(session, user.username, "guardrail.isolation",
                 details={"enforced": body.value})
    return {"isolation_enforced": body.value}


@router.get("/admin/audit", tags=["admin"])
def audit_log(
    limit: int = 200,
    user: User = Depends(require_roles(Role.ADMIN, Role.DIRECTOR, Role.OBSERVER)),
    session: Session = Depends(get_session),
):
    from .models import AuditLog
    rows = session.exec(
        select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    ).all()
    return rows


@router.get("/admin/audit/verify", tags=["admin"])
def audit_verify(
    user: User = Depends(require_roles(Role.ADMIN, Role.DIRECTOR)),
    session: Session = Depends(get_session),
):
    return audit.verify_chain(session)


# --------------------------------------------------------------------------- #
# WebSocket live feed
# --------------------------------------------------------------------------- #
@router.websocket("/ws/scenarios/{scenario_id}")
async def ws_feed(websocket: WebSocket, scenario_id: int):
    await hub.connect(scenario_id, websocket)
    try:
        while True:
            await websocket.receive_text()  # keepalive / ignore inbound
    except WebSocketDisconnect:
        await hub.disconnect(scenario_id, websocket)
    except Exception:
        await hub.disconnect(scenario_id, websocket)
