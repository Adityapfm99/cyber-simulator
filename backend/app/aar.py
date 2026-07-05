"""§2 After-Action Review (AAR) report generation.

Produces a structured AAR for a scenario: incident timeline, response-time
metrics against targets, an SOP gap analysis (which phases missed target), and a
PDF export. If reportlab is unavailable the same content is emitted as HTML so
the feature degrades gracefully.
"""
from __future__ import annotations

import io
from datetime import datetime

from sqlmodel import Session, select

from . import scoring
from .config import TARGET_TTC, TARGET_TTD, TARGET_TTR, TARGET_TTT
from .models import AuditLog, Event, Incident, Scenario

_TARGETS = {"TTD": TARGET_TTD, "TTT": TARGET_TTT, "TTC": TARGET_TTC, "TTR": TARGET_TTR}
_PHASE_LABEL = {
    "TTD": "Detect", "TTT": "Triage", "TTC": "Contain", "TTR": "Recover",
}


def _fmt(sec: float | None) -> str:
    if sec is None:
        return "—"
    m, s = divmod(int(sec), 60)
    return f"{m}m{s:02d}s"


def build_report(session: Session, scenario_id: int) -> dict:
    scenario = session.get(Scenario, scenario_id)
    if scenario is None:
        raise ValueError("Scenario not found")
    incidents = session.exec(
        select(Incident).where(Incident.scenario_id == scenario_id)
    ).all()

    gaps: list[str] = []
    incident_rows = []
    for inc in incidents:
        m = scoring.metrics(inc)
        row = {
            "id": inc.id, "title": inc.title, "status": inc.status,
            "assigned_to": inc.assigned_to or "unassigned",
            "score": inc.score or 0, "metrics": m,
        }
        for phase, target in _TARGETS.items():
            val = m.get(phase)
            if val is None:
                gaps.append(f"Incident #{inc.id} '{inc.title}': "
                            f"{_PHASE_LABEL[phase]} phase never completed.")
            elif val > target:
                gaps.append(f"Incident #{inc.id} '{inc.title}': "
                            f"{_PHASE_LABEL[phase]} took {_fmt(val)} "
                            f"(target {_fmt(target)}).")
        incident_rows.append(row)

    scores = [i.score or 0 for i in incidents]
    avg = round(sum(scores) / len(scores)) if scores else 0

    return {
        "scenario": {
            "id": scenario.id, "name": scenario.name, "status": scenario.status,
            "deployed_at": scenario.deployed_at.isoformat() if scenario.deployed_at else None,
        },
        "summary": {
            "incident_count": len(incidents),
            "average_score": avg,
            "gap_count": len(gaps),
        },
        "incidents": incident_rows,
        "sop_gaps": gaps,
        "targets": {k: _fmt(v) for k, v in _TARGETS.items()},
    }


def render_pdf(session: Session, scenario_id: int) -> tuple[bytes, str]:
    """Return (bytes, media_type). PDF if reportlab present, else HTML."""
    report = build_report(session, scenario_id)
    try:
        return _reportlab_pdf(report), "application/pdf"
    except Exception:
        return _html(report).encode(), "text/html"


def _reportlab_pdf(report: dict) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title="After-Action Review")
    styles = getSampleStyleSheet()
    flow = []

    s = report["scenario"]
    flow.append(Paragraph("After-Action Review (AAR)", styles["Title"]))
    flow.append(Paragraph(f"Scenario: <b>{s['name']}</b> (#{s['id']})", styles["Normal"]))
    flow.append(Paragraph(f"Status: {s['status']}", styles["Normal"]))
    flow.append(Spacer(1, 6 * mm))

    summ = report["summary"]
    flow.append(Paragraph(
        f"Incidents: {summ['incident_count']} &nbsp;|&nbsp; "
        f"Average score: {summ['average_score']}/100 &nbsp;|&nbsp; "
        f"SOP gaps: {summ['gap_count']}", styles["Heading3"]))
    flow.append(Spacer(1, 4 * mm))

    header = ["#", "Incident", "Status", "Analyst", "TTD", "TTT", "TTC", "TTR", "Score"]
    data = [header]
    for inc in report["incidents"]:
        m = inc["metrics"]
        data.append([
            str(inc["id"]), inc["title"][:28], inc["status"], inc["assigned_to"],
            _fmt(m["TTD"]), _fmt(m["TTT"]), _fmt(m["TTC"]), _fmt(m["TTR"]),
            str(inc["score"]),
        ])
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
    ]))
    flow.append(table)
    flow.append(Spacer(1, 6 * mm))

    flow.append(Paragraph("SOP Gap Analysis", styles["Heading2"]))
    if report["sop_gaps"]:
        for g in report["sop_gaps"]:
            flow.append(Paragraph(f"• {g}", styles["Normal"]))
    else:
        flow.append(Paragraph("No SOP gaps — all phases met target times.", styles["Normal"]))

    doc.build(flow)
    return buf.getvalue()


def _html(report: dict) -> str:
    s = report["scenario"]
    rows = "".join(
        f"<tr><td>{i['id']}</td><td>{i['title']}</td><td>{i['status']}</td>"
        f"<td>{i['assigned_to']}</td><td>{_fmt(i['metrics']['TTD'])}</td>"
        f"<td>{_fmt(i['metrics']['TTT'])}</td><td>{_fmt(i['metrics']['TTC'])}</td>"
        f"<td>{_fmt(i['metrics']['TTR'])}</td><td>{i['score']}</td></tr>"
        for i in report["incidents"]
    )
    gaps = "".join(f"<li>{g}</li>" for g in report["sop_gaps"]) or "<li>No gaps.</li>"
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>AAR — {s['name']}</title></head><body>
<h1>After-Action Review</h1>
<h2>{s['name']} (#{s['id']}) — {s['status']}</h2>
<table border="1" cellpadding="4"><tr><th>#</th><th>Incident</th><th>Status</th>
<th>Analyst</th><th>TTD</th><th>TTT</th><th>TTC</th><th>TTR</th><th>Score</th></tr>
{rows}</table>
<h2>SOP Gap Analysis</h2><ul>{gaps}</ul>
</body></html>"""
