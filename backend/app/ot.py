"""MOD-03 — OT/ICS Digital Twin telemetry.

Produces SCADA/HMI-style readings for base facilities (electrical power + HVAC)
derived from the OT node status in a scenario:

  * node ``up``          → nominal readings (green)
  * node ``compromised`` → out-of-range readings + alarms (a cyberattack drove
    an operational failure: overvoltage, cooling disabled, PLC setpoint override)
  * node ``quarantined`` → isolated: last-known values frozen, degraded
  * node ``halted``/``destroyed`` → offline

Readings carry a small time-based wobble so the HMI looks live.
"""
from __future__ import annotations

import math
import time

from sqlmodel import Session, select

from .models import Node, Scenario


def _wobble(amp: float) -> float:
    # Smooth pseudo-live variation without RNG.
    return amp * math.sin(time.time() * 1.7)


def _metric(key, label, value, unit, lo, hi, nom_lo, nom_hi, alarm):
    return {
        "key": key, "label": label, "value": round(value, 1), "unit": unit,
        "min": lo, "max": hi, "nominal": [nom_lo, nom_hi], "alarm": alarm,
    }


def _power(status: str) -> dict:
    if status == "compromised":
        metrics = [
            _metric("voltage", "Voltage", 261 + _wobble(3), "V", 0, 300, 210, 230, True),
            _metric("frequency", "Frequency", 53.2 + _wobble(0.3), "Hz", 45, 55, 49.5, 50.5, True),
            _metric("load", "Load", 104 + _wobble(4), "%", 0, 120, 0, 80, True),
        ]
        return {"state": "critical", "metrics": metrics,
                "indicators": [{"label": "Breaker", "value": "TRIPPED", "alarm": True}],
                "alarms": ["Overvoltage detected (PLC setpoint override)",
                           "Load over threshold — blackout risk"]}
    if status in ("quarantined", "halted", "destroyed"):
        off = status != "quarantined"
        return {"state": "offline" if off else "isolated",
                "metrics": [
                    _metric("voltage", "Voltage", 0 if off else 219, "V", 0, 300, 210, 230, off),
                    _metric("frequency", "Frequency", 0 if off else 50, "Hz", 45, 55, 49.5, 50.5, off),
                    _metric("load", "Load", 0 if off else 58, "%", 0, 120, 0, 80, False),
                ],
                "indicators": [{"label": "Breaker", "value": "OPEN" if off else "HOLD", "alarm": off}],
                "alarms": (["Power supply OFFLINE"] if off else ["PLC isolated — values frozen"])}
    return {"state": "operational", "metrics": [
        _metric("voltage", "Voltage", 220 + _wobble(1.5), "V", 0, 300, 210, 230, False),
        _metric("frequency", "Frequency", 50 + _wobble(0.08), "Hz", 45, 55, 49.5, 50.5, False),
        _metric("load", "Load", 60 + _wobble(4), "%", 0, 120, 0, 80, False),
    ], "indicators": [{"label": "Breaker", "value": "CLOSED", "alarm": False}], "alarms": []}


def _hvac(status: str) -> dict:
    if status == "compromised":
        return {"state": "critical", "metrics": [
            _metric("temp", "Room Temp", 41 + _wobble(1.5), "°C", 10, 55, 18, 26, True),
            _metric("setpoint", "Setpoint", 40, "°C", 10, 45, 20, 24, True),
            _metric("humidity", "Humidity", 68 + _wobble(3), "%", 0, 100, 40, 60, True),
        ], "indicators": [{"label": "Fan", "value": "STOPPED", "alarm": True}],
            "alarms": ["Cooling disabled (setpoint override)",
                       "Server room temp exceeds safe limit"]}
    if status in ("quarantined", "halted", "destroyed"):
        off = status != "quarantined"
        return {"state": "offline" if off else "isolated", "metrics": [
            _metric("temp", "Room Temp", 0 if off else 24, "°C", 10, 55, 18, 26, off),
            _metric("setpoint", "Setpoint", 22, "°C", 10, 45, 20, 24, False),
            _metric("humidity", "Humidity", 0 if off else 50, "%", 0, 100, 40, 60, False),
        ], "indicators": [{"label": "Fan", "value": "OFF" if off else "HOLD", "alarm": off}],
            "alarms": (["HVAC OFFLINE"] if off else ["HMI isolated — values frozen"])}
    return {"state": "operational", "metrics": [
        _metric("temp", "Room Temp", 22 + _wobble(0.6), "°C", 10, 55, 18, 26, False),
        _metric("setpoint", "Setpoint", 22, "°C", 10, 45, 20, 24, False),
        _metric("humidity", "Humidity", 47 + _wobble(2), "%", 0, 100, 40, 60, False),
    ], "indicators": [{"label": "Fan", "value": "RUNNING", "alarm": False}], "alarms": []}


# Which node role drives which HMI facility.
_FACILITIES = [
    ("plc-power", "⚡ Electrical Power", _power),
    ("plc-hvac", "❄️ Cooling / HVAC", _hvac),
]


def telemetry(session: Session, scenario_id: int) -> dict:
    scenario = session.get(Scenario, scenario_id)
    if scenario is None:
        raise ValueError("Scenario not found")
    nodes = session.exec(select(Node).where(Node.scenario_id == scenario_id)).all()
    by_role = {n.role: n for n in nodes}

    facilities = []
    overall = "operational"
    rank = {"operational": 0, "isolated": 1, "offline": 2, "critical": 3}
    for role, label, fn in _FACILITIES:
        node = by_role.get(role)
        if node is None:
            continue
        data = fn(node.status)
        data.update({"name": node.name, "label": label, "role": role, "node_status": node.status})
        facilities.append(data)
        if rank[data["state"]] > rank[overall]:
            overall = data["state"]

    # HMI console (scada-hmi) status line.
    hmi = by_role.get("hmi")
    hmi_status = hmi.status if hmi else "n/a"

    all_alarms = [f"{f['label']}: {a}" for f in facilities for a in f["alarms"]]
    return {
        "scenario": {"id": scenario.id, "name": scenario.name},
        "has_ot": bool(facilities),
        "overall_state": overall,
        "hmi_status": hmi_status,
        "facilities": facilities,
        "alarms": all_alarms,
    }
