// MOD-02 Web Security Lab — vuln registry, exploit tester, patch controls.
import React, { useEffect, useState } from "react";
import { A, getRole } from "./api.js";

const CAN_PATCH = ["Admin", "SOC Analyst"];

export default function WebSecLab({ open, onClose }) {
  const [reg, setReg] = useState(null);
  const [result, setResult] = useState({});
  const [err, setErr] = useState("");
  const canPatch = CAN_PATCH.includes(getRole());

  const load = () => A.websecRegistry().then(setReg).catch((e) => setErr(e.message));
  useEffect(() => { if (open) load(); }, [open]);

  if (!open) return null;

  const wrap = (fn) => async (...a) => {
    setErr("");
    try { return await fn(...a); } catch (e) { setErr(e.message); }
  };
  const patch = wrap(async (vuln, patched) => { await A.websecPatch(vuln, patched); await load(); });
  const exploit = wrap(async (vuln) => {
    try {
      const r = await A.websecExploit(vuln);
      setResult((p) => ({ ...p, [vuln]: r }));
    } catch (e) {
      setResult((p) => ({ ...p, [vuln]: { blocked: true, detail: e.message } }));
    }
    await load();
  });

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ width: "min(820px,100%)" }}>
        <div className="row">
          <h2 style={{ margin: 0 }}>🕸 Web Security Lab (MOD-02)</h2>
          <span style={{ flex: 1 }} />
          <span style={{ fontSize: 12, color: "var(--muted)", marginRight: 10 }}>
            Hardening: <b style={{ color: reg && reg.hardening_score === 100 ? "var(--ok)" : "var(--warn)" }}>
              {reg ? `${reg.patched}/${reg.total} (${reg.hardening_score}%)` : "…"}</b>
          </span>
          <button className="ghost" onClick={onClose}>✕ Close</button>
        </div>
        <p style={{ fontSize: 12, color: "var(--muted)", marginTop: 6 }}>
          Aplikasi web rentan (OWASP Top 10) — data 100% dummy & tersandbox. Blue team
          bertugas <b>uji exploit</b> lalu <b>patch</b> tiap kerentanan.
        </p>
        <div className="err">{err}</div>

        {!reg ? <div className="empty">Loading…</div> : reg.vulnerabilities.map((v) => (
          <div key={v.id} className="inc" style={{ borderColor: v.patched ? "var(--ok)" : "var(--border)" }}>
            <div className="row">
              <span className="title">{v.name}</span>
              <span style={{ flex: 1 }} />
              <span className="status-tag" style={{
                background: v.patched ? "#10281f" : "#3a1414",
                color: v.patched ? "var(--ok)" : "var(--crit)",
              }}>{v.patched ? "PATCHED" : "VULNERABLE"}</span>
            </div>
            <div style={{ fontSize: 11, color: "var(--muted)", margin: "4px 0" }}>
              {v.owasp} · <code>{v.endpoint}</code>
            </div>
            <div style={{ fontSize: 11, color: "var(--muted)" }}>{v.hint}</div>
            <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 3 }}>
              Percobaan: {v.attempts} · exploit sukses: {v.successful_exploits}
            </div>
            <div className="row" style={{ marginTop: 8, gap: 8 }}>
              <button onClick={() => exploit(v.id)}>⚡ Uji exploit</button>
              {canPatch && (v.patched
                ? <button onClick={() => patch(v.id, false)}>Un-patch</button>
                : <button className="primary" onClick={() => patch(v.id, true)}>🔧 Patch</button>)}
            </div>
            {result[v.id] && (
              <pre style={{
                marginTop: 8, background: "var(--panel-2)", padding: 8, borderRadius: 6,
                fontSize: 10.5, overflow: "auto", maxHeight: 160, whiteSpace: "pre-wrap",
                color: result[v.id].exploited ? "var(--crit)" : (result[v.id].blocked ? "var(--ok)" : "var(--text)"),
              }}>{JSON.stringify(result[v.id], null, 2)}</pre>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
