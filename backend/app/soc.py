"""§3 SOC Simulator — SIEM emulator producing fake logs.

Two log streams:
  * baseline — harmless dummy Firewall/EDR/DNS/Proxy chatter so the lab looks
    "alive" even when nothing is happening.
  * attack — higher-severity lines produced when an event is injected, giving
    the SOC analyst something to detect.

Log generation is deterministic-ish (index-seeded) because scenarios run in an
environment without Math.random/Date.now guarantees; variety comes from rotating
templates rather than true randomness.
"""
from __future__ import annotations

import time

from sqlmodel import Session, select

from .models import LogEntry, Node, as_utc, utcnow

SOURCES = ["firewall", "edr", "dns", "proxy"]

_BASELINE_TEMPLATES = {
    "firewall": "ACCEPT tcp {src}:{sport} -> {dst}:443 policy=allow-web",
    "edr": "process_start host={dst} image=svchost.exe signed=true",
    "dns": "query {dst} name=update.internal.lab type=A rcode=NOERROR",
    "proxy": "GET http://intranet.lab/portal user={who} status=200",
}

_WHO = ["trainee-01", "trainee-02", "operator-a", "npc-user"]


def _pick(seq, i):
    return seq[i % len(seq)]


def lazy_fill(session: Session, scenario_id: int, max_batches: int = 6) -> list[LogEntry]:
    """Generate the baseline traffic that *would* have accrued since the last log.

    Used in serverless mode where there is no always-on ticker: each time the
    client polls for logs we materialize roughly one batch per elapsed 2s window
    (capped), keeping the lab feeling "alive" without a background process.
    """
    last = session.exec(
        select(LogEntry).where(LogEntry.scenario_id == scenario_id)
        .order_by(LogEntry.id.desc())
    ).first()
    if last is None:
        batches = 1
    else:
        elapsed = (utcnow() - as_utc(last.ts)).total_seconds()
        batches = int(elapsed // 2)
    batches = max(0, min(batches, max_batches))
    created: list[LogEntry] = []
    base = int(time.time())
    for k in range(batches):
        logs = generate_baseline(session, scenario_id, base + k)
        for lg in logs:
            session.add(lg)
        created.extend(logs)
    if created:
        session.commit()
    return created


def generate_baseline(session: Session, scenario_id: int, seed: int) -> list[LogEntry]:
    """Emit one baseline line per source, seeded by ``seed``."""
    nodes = session.exec(select(Node).where(Node.scenario_id == scenario_id)).all()
    if not nodes:
        return []
    ips = [n.ip for n in nodes if n.ip] or ["10.0.0.1"]
    out = []
    for j, source in enumerate(SOURCES):
        dst = _pick(ips, seed + j)
        src = _pick(ips, seed + j + 1)
        msg = _BASELINE_TEMPLATES[source].format(
            src=src, dst=dst, sport=1024 + ((seed + j) % 60000),
            who=_pick(_WHO, seed + j),
        )
        out.append(LogEntry(
            scenario_id=scenario_id, source=source, severity="info",
            src_ip=src, dst_ip=dst, message=msg,
        ))
    return out


# Attack log templates keyed by event type — the "tells" an analyst hunts for.
_ATTACK_TEMPLATES = {
    "portscan": [
        ("firewall", "warning", "DROP tcp {src}:* -> {dst}:1-1024 SYN scan detected"),
        ("edr", "notice", "network_recon host={dst} many_connections_from={src}"),
    ],
    "bruteforce": [
        ("edr", "warning", "auth_failure host={dst} user=blue-lead attempts=57 src={src}"),
        ("firewall", "notice", "ACCEPT tcp {src} -> {dst}:22 repeated"),
    ],
    "phishing": [
        ("proxy", "warning", "GET http://vendor-portal.lab/login?token=... user=trainee-02 blocked=false"),
        ("dns", "notice", "query {dst} name=vendor-portal.lab type=A rcode=NOERROR"),
    ],
    "lateral_move": [
        ("edr", "warning", "remote_exec host={dst} tool=psexec-like src={src}"),
        ("firewall", "notice", "ACCEPT tcp {src} -> {dst}:445 smb"),
    ],
    "ransomware": [
        ("edr", "critical", "mass_file_rename host={dst} ext=.locked rate=high (DUMMY drill)"),
        ("edr", "critical", "shadow_copy_delete host={dst} (DUMMY drill)"),
        ("proxy", "warning", "POST http://drop.lab/key host={dst} blocked=true"),
    ],
    "data_exfil": [
        ("proxy", "critical", "POST http://exfil.lab/upload bytes=5000000 host={dst}"),
        ("dns", "warning", "query {dst} name=long-encoded-string.exfil.lab type=TXT"),
    ],
    "dns_tunnel": [
        ("dns", "warning", "query {dst} name=aGVsbG8.tunnel.lab type=TXT rcode=NOERROR"),
    ],
    "ot_fault": [
        ("edr", "critical", "OT ALARM hmi={dst} setpoint_override plc=power (DUMMY)"),
        ("firewall", "warning", "modbus write {src} -> {dst}:502 unexpected"),
    ],
    "c2_jamming": [
        ("edr", "warning", "c2_link degraded node={dst} latency_spike jitter=high (DUMMY)"),
    ],
    "supply_chain_anomaly": [
        ("edr", "critical", "vendor artifact hash_mismatch node={dst} expected!=actual"),
        ("proxy", "warning", "TLS cert expired vendor-gw presented_by={dst}"),
    ],
}


def generate_attack(
    session: Session, scenario_id: int, event_type: str, target_ip: str,
    src_ip: str, event_id: int,
) -> list[LogEntry]:
    templates = _ATTACK_TEMPLATES.get(event_type, [
        ("edr", "warning", "anomalous activity host={dst} src={src}")
    ])
    out = []
    for source, severity, tmpl in templates:
        out.append(LogEntry(
            scenario_id=scenario_id, source=source, severity=severity,
            src_ip=src_ip, dst_ip=target_ip,
            message=tmpl.format(src=src_ip or "10.66.66.66", dst=target_ip or "unknown"),
            event_id=event_id,
        ))
    return out
