// MOD-03 OT/ICS Digital Twin — SCADA/HMI gauges for power & HVAC.
// Gauges read green when nominal and turn red/alarm when the OT node is attacked.
import React, { useEffect, useRef, useState } from "react";
import { A } from "./api.js";

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

function polar(cx, cy, r, deg) {
  const a = (deg * Math.PI) / 180;
  return { x: cx + r * Math.cos(a), y: cy - r * Math.sin(a) };
}
// Sample an arc from startDeg to endDeg into a polyline (avoids arc-flag pitfalls).
function arcPoints(cx, cy, r, startDeg, endDeg, n = 32) {
  const pts = [];
  for (let i = 0; i <= n; i++) {
    const d = startDeg + ((endDeg - startDeg) * i) / n;
    const p = polar(cx, cy, r, d);
    pts.push(`${p.x.toFixed(1)},${p.y.toFixed(1)}`);
  }
  return pts.join(" ");
}

function Gauge({ m }) {
  const cx = 60, cy = 66, r = 46;
  const f = clamp((m.value - m.min) / (m.max - m.min || 1), 0, 1);
  const valDeg = 180 - f * 180;
  const color = m.alarm ? "#ff5c5c" : "#35d0a5";
  // nominal band angles
  const nlo = 180 - clamp((m.nominal[1] - m.min) / (m.max - m.min), 0, 1) * 180;
  const nhi = 180 - clamp((m.nominal[0] - m.min) / (m.max - m.min), 0, 1) * 180;
  const needle = polar(cx, cy, r - 6, valDeg);
  return (
    <div style={{ textAlign: "center", width: 120 }}>
      <div style={{ fontSize: 11, color: "var(--muted)" }}>{m.label}</div>
      <svg viewBox="0 0 120 78" width="120" height="78">
        <polyline points={arcPoints(cx, cy, r, 180, 0)} fill="none" stroke="#26374a" strokeWidth="8" strokeLinecap="round" />
        <polyline points={arcPoints(cx, cy, r, nlo, nhi)} fill="none" stroke="#2f6f5a" strokeWidth="8" opacity="0.5" />
        <polyline points={arcPoints(cx, cy, r, 180, valDeg)} fill="none" stroke={color} strokeWidth="8" strokeLinecap="round" />
        <line x1={cx} y1={cy} x2={needle.x} y2={needle.y} stroke={color} strokeWidth="2.5" />
        <circle cx={cx} cy={cy} r="3.5" fill={color} />
      </svg>
      <div style={{ fontSize: 17, fontWeight: 700, color, marginTop: -8 }}>
        {m.value}<span style={{ fontSize: 10, color: "var(--muted)" }}> {m.unit}</span>
      </div>
    </div>
  );
}

const STATE_COLOR = {
  operational: "var(--ok)", critical: "var(--crit)",
  offline: "var(--muted)", isolated: "var(--warn)",
};

export default function OTView({ open, onClose, scenarioId }) {
  const [ot, setOt] = useState(null);
  const [err, setErr] = useState("");
  const timer = useRef(null);

  useEffect(() => {
    if (!open || !scenarioId) return;
    const load = () => A.ot(scenarioId).then(setOt).catch((e) => setErr(e.message));
    load();
    timer.current = setInterval(load, 2000);
    return () => clearInterval(timer.current);
  }, [open, scenarioId]);

  if (!open) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ width: "min(760px,100%)" }}>
        <div className="row">
          <h2 style={{ margin: 0 }}>🏭 OT/ICS Digital Twin — HMI (MOD-03)</h2>
          <span style={{ flex: 1 }} />
          {ot && (
            <span className="status-tag" style={{
              background: "#0e141c", color: STATE_COLOR[ot.overall_state], border: "1px solid",
            }}>{(ot.overall_state || "").toUpperCase()}</span>
          )}
          <button className="ghost" onClick={onClose} style={{ marginLeft: 10 }}>✕ Close</button>
        </div>
        <div className="err">{err}</div>

        {!scenarioId ? (
          <div className="empty">Select a scenario in the left panel (an OT/ICS Base one)
            first, then reopen this HMI.</div>
        ) : !ot ? <div className="empty">Loading…</div> : !ot.has_ot ? (
          <div className="empty">This scenario has no OT/ICS facilities. Deploy the
            "OT/ICS Base" scenario, then inject <code>ot_fault</code> to see the failure.</div>
        ) : (
          <>
            {ot.facilities.map((f) => (
              <div key={f.name} className="inc" style={{ borderColor: STATE_COLOR[f.state] }}>
                <div className="row">
                  <span className="title">{f.label} <span style={{ color: "var(--muted)", fontWeight: 400 }}>({f.name})</span></span>
                  <span style={{ flex: 1 }} />
                  {f.indicators.map((ind) => (
                    <span key={ind.label} className="status-tag" style={{
                      marginLeft: 6, background: ind.alarm ? "#3a1414" : "#10281f",
                      color: ind.alarm ? "var(--crit)" : "var(--ok)",
                    }}>{ind.label}: {ind.value}</span>
                  ))}
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6, justifyContent: "center", marginTop: 6 }}>
                  {f.metrics.map((m) => <Gauge key={m.key} m={m} />)}
                </div>
                {f.alarms.length > 0 && (
                  <ul style={{ margin: "4px 0 0", paddingLeft: 18, fontSize: 11.5, color: "var(--crit)" }}>
                    {f.alarms.map((a, i) => <li key={i}>⚠ {a}</li>)}
                  </ul>
                )}
              </div>
            ))}
            <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 6 }}>
              HMI console: {ot.hmi_status} · green gauge = nominal, red = alarm from attack.
              Restore the OT node (Containment panel) to recover.
            </div>
          </>
        )}
      </div>
    </div>
  );
}
