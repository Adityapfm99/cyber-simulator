// Commander leadership console — the §3 C2 Resilience picture.
// Under simulated jamming the feed intentionally shows stale/conflicting data.
import React, { useEffect, useState } from "react";
import { A, getUsername, getRole } from "./api.js";
import Help from "./Help.jsx";

const FAC_COLOR = {
  operational: "var(--ok)",
  degraded: "var(--warn)",
  critical: "var(--crit)",
  offline: "var(--muted)",
  unknown: "var(--muted)",
};

export default function CommanderView({ onLogout }) {
  const [scenarios, setScenarios] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [c2, setC2] = useState(null);
  const [showHelp, setShowHelp] = useState(false);

  useEffect(() => {
    A.scenarios().then((s) => {
      setScenarios(s);
      const running = s.find((x) => x.status === "running") || s[0];
      if (running) setSelectedId(running.id);
    });
  }, []);

  const load = (id) => A.c2(id).then(setC2).catch(() => setC2(null));

  useEffect(() => {
    if (!selectedId) return;
    load(selectedId);
    const poll = setInterval(() => load(selectedId), 3000);
    return () => clearInterval(poll);
  }, [selectedId]);

  const degraded = c2?.c2_link?.status === "degraded";

  return (
    <>
      <div className="topbar">
        <h1>📡 COMMANDER · C2 CONSOLE</h1>
        <select value={selectedId || ""} onChange={(e) => setSelectedId(Number(e.target.value))}>
          {scenarios.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.status})</option>)}
        </select>
        <span className="spacer" style={{ flex: 1 }} />
        <span className="role-badge">{getUsername()} · {getRole()}</span>
        <button className="help-btn ghost" onClick={() => setShowHelp(true)}>📖 Guide</button>
        <button className="ghost" onClick={onLogout}>Logout</button>
      </div>
      <Help open={showHelp} onClose={() => setShowHelp(false)} />

      {!c2 ? (
        <div className="empty" style={{ marginTop: 40 }}>No scenario data. Ask the Exercise Director to deploy one.</div>
      ) : (
        <div style={{ padding: 16, display: "grid", gap: 14, maxWidth: 1100, margin: "0 auto" }}>
          {/* C2 link banner */}
          <div className="panel" style={{
            borderColor: degraded ? "var(--crit)" : "var(--ok)",
            background: degraded ? "#2a1010" : "var(--panel)",
          }}>
            <div className="row">
              <div>
                <div style={{ fontSize: 16, fontWeight: 700, color: degraded ? "var(--crit)" : "var(--ok)" }}>
                  {degraded ? "⚠ C2 LINK DEGRADED — JAMMING DETECTED" : "✓ C2 LINK NOMINAL"}
                </div>
                <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 4 }}>{c2.c2_link.note}</div>
              </div>
              <span style={{ flex: 1 }} />
              <div style={{ textAlign: "right", fontSize: 11, color: "var(--muted)" }}>
                Last sync<br /><span style={{ color: degraded ? "var(--crit)" : "var(--text)" }}>{c2.last_sync}</span>
              </div>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
            {/* Facilities */}
            <div className="panel">
              <h2>Base Facilities (OT/ICS) · {c2.facility_state}</h2>
              {c2.facilities.length === 0 && <div className="empty">No OT facilities in this scenario.</div>}
              {c2.facilities.map((f) => (
                <div key={f.name} className="row" style={{ padding: "6px 0", borderBottom: "1px solid #182230" }}>
                  <span style={{ fontWeight: 600 }}>{f.name}</span>
                  <span style={{ color: "var(--muted)", marginLeft: 8, fontSize: 12 }}>{f.role}</span>
                  <span style={{ flex: 1 }} />
                  <span style={{ color: FAC_COLOR[f.state], fontWeight: 600, textTransform: "uppercase", fontSize: 12 }}>
                    {f.state}
                  </span>
                </div>
              ))}
            </div>

            {/* Vendor integrity */}
            <div className="panel">
              <h2>Supply-Chain / Vendor Integrity</h2>
              <div style={{
                fontSize: 15, fontWeight: 700,
                color: c2.vendor_integrity.status === "ok" ? "var(--ok)" : "var(--crit)",
              }}>
                {c2.vendor_integrity.status === "ok" ? "✓ No anomalies" : "⚠ Anomalies detected"}
              </div>
              <ul style={{ margin: "8px 0 0", paddingLeft: 18, fontSize: 12, color: "var(--warn)" }}>
                {c2.vendor_integrity.issues.map((i, k) => <li key={k}>{i}</li>)}
              </ul>
            </div>
          </div>

          {/* Situation reports — the conflict is the point under jamming */}
          <div className="panel">
            <h2>Situation Reports {!c2.data_reliable && <span style={{ color: "var(--crit)" }}>· DATA UNRELIABLE</span>}</h2>
            <div style={{ display: "grid", gridTemplateColumns: `repeat(${c2.situation_reports.length}, 1fr)`, gap: 10 }}>
              {c2.situation_reports.map((r, k) => (
                <div key={k} style={{
                  border: "1px solid var(--border)", borderRadius: 8, padding: 12,
                  background: "var(--panel-2)",
                }}>
                  <div style={{ fontSize: 12, color: "var(--muted)" }}>{r.source}</div>
                  <div style={{ fontSize: 28, fontWeight: 700 }}>{r.open_incidents}</div>
                  <div style={{ fontSize: 11, color: "var(--muted)" }}>open incidents</div>
                  <div style={{ fontSize: 11, marginTop: 6, color: r.confidence === "high" ? "var(--ok)" : "var(--warn)" }}>
                    confidence: {r.confidence}
                  </div>
                  <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>{r.note}</div>
                </div>
              ))}
            </div>
            {!c2.data_reliable && (
              <div style={{ marginTop: 10, fontSize: 12, color: "var(--crit)" }}>
                ⚠ Feeds disagree — reconcile before acting on these figures.
              </div>
            )}
          </div>

          {/* Incident summary */}
          <div className="panel">
            <h2>Incident Summary</h2>
            <div className="row" style={{ gap: 24 }}>
              <div><div style={{ fontSize: 24, fontWeight: 700 }}>{c2.incident_summary.total}</div><div style={{ fontSize: 11, color: "var(--muted)" }}>total</div></div>
              <div><div style={{ fontSize: 24, fontWeight: 700, color: "var(--warn)" }}>{c2.incident_summary.open}</div><div style={{ fontSize: 11, color: "var(--muted)" }}>open</div></div>
              <div><div style={{ fontSize: 24, fontWeight: 700, color: "var(--ok)" }}>{c2.incident_summary.recovered}</div><div style={{ fontSize: 11, color: "var(--muted)" }}>recovered</div></div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
