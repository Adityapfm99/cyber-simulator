"""FastAPI application entrypoint + background simulation ticker."""
from __future__ import annotations

import asyncio
import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from . import config, events, guardrails, scenarios, soc
from .database import engine, init_db
from .models import LogEntry, Scenario, ScenarioStatus
from .realtime import hub
from .routes import router


def _ensure_ready() -> None:
    """Create tables and (optionally) seed demo users. Idempotent."""
    init_db()
    if config.AUTO_SEED:
        try:
            from .seed import seed
            seed(verbose=False)
        except Exception as exc:  # never let seeding crash startup
            print(f"[startup] auto-seed skipped: {exc}")

_tick = 0


async def _simulation_loop() -> None:
    """Every ~2s: emit baseline SOC traffic and fire due scheduled events.

    Runs against running (non-halted) scenarios only, so the kill switch and
    isolation guardrails naturally gate all background activity.
    """
    global _tick
    while True:
        try:
            await asyncio.sleep(2)
            _tick += 1
            with Session(engine, expire_on_commit=False) as session:
                if guardrails.is_kill_switch_engaged(session):
                    continue
                running = session.exec(
                    select(Scenario).where(Scenario.status == ScenarioStatus.RUNNING)
                ).all()
                for sc in running:
                    # Baseline dummy traffic so the lab "looks alive".
                    new_logs = soc.generate_baseline(session, sc.id, _tick)
                    for lg in new_logs:
                        session.add(lg)
                    session.commit()
                    for lg in new_logs:
                        await hub.publish(sc.id, {"kind": "log", "data": {
                            "source": lg.source, "severity": lg.severity,
                            "message": lg.message, "src_ip": lg.src_ip,
                            "dst_ip": lg.dst_ip,
                        }})

                # Scheduled event injection.
                for ev in events.due_scheduled(session):
                    result = events.inject(session, "scheduler", ev.id)
                    sid = result["event"].scenario_id
                    for lg in result["logs"]:
                        await hub.publish(sid, {"kind": "log", "data": lg})
                    await hub.publish(sid, {"kind": "event", "data": {
                        "title": result["event"].title,
                        "type": result["event"].type,
                        "incident_id": result["incident"].id,
                    }})
                    await hub.publish(sid, {"kind": "topology",
                                            "data": scenarios.topology(session, sid)})
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # keep the loop alive on transient errors
            print(f"[sim-loop] error: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_ready()
    task = None
    if config.RUN_BACKGROUND:
        task = asyncio.create_task(_simulation_loop())
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


app = FastAPI(
    title="Cyber Simulator Demo — Defensive Cyber-Range",
    description="MVP software prototype of the Spektek defensive cyber simulator.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# All API routes live under /api so a single Vercel deployment can serve the
# static frontend at / and route /api/* to this function.
app.include_router(router, prefix="/api")


@app.get("/api/health", tags=["meta"])
@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "tick": _tick, "background": config.RUN_BACKGROUND}
