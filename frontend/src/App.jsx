import React, { useEffect, useRef, useState, useCallback } from "react";
import { A, login, logout, getToken, getRole, getUsername, openFeed } from "./api.js";
import TopologyGraph from "./TopologyGraph.jsx";
import CommanderView from "./CommanderView.jsx";

const TARGETS = { TTD: 300, TTT: 600, TTC: 1800, TTR: 3600 };
const CAN = {
  manage: ["Admin", "Exercise Director"],
  respond: ["Admin", "SOC Analyst"],
};

function fmt(sec) {
  if (sec == null) return "—";
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}m${String(s).padStart(2, "0")}s`;
}

// --------------------------------------------------------------------------- //
function Login({ onDone }) {
  const [u, setU] = useState("director");
  const [p, setP] = useState("director123");
  const [err, setErr] = useState("");
  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    try {
      await login(u, p);
      onDone();
    } catch (ex) {
      setErr(ex.message);
    }
  };
  return (
    <div className="login-wrap">
      <div className="login-card">
        <h1>🛡️ Cyber Simulator</h1>
        <p>Defensive Cyber-Range — Exercise Director Console</p>
        <form onSubmit={submit}>
          <input value={u} onChange={(e) => setU(e.target.value)} placeholder="username" />
          <input type="password" value={p} onChange={(e) => setP(e.target.value)} placeholder="password" />
          <button className="primary" type="submit">Sign in</button>
        </form>
        <div className="err">{err}</div>
        <div className="demo-hint">
          Demo accounts:<br />
          <code>admin/admin123</code> · <code>director/director123</code><br />
          <code>analyst/analyst123</code> · <code>commander/commander123</code> · <code>observer/observer123</code>
        </div>
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- //
function ScenarioColumn({ scenarios, selectedId, onSelect, onCreate, role, reload }) {
  const [templates, setTemplates] = useState([]);
  const [tpl, setTpl] = useState("");
  const [name, setName] = useState("");
  const canManage = CAN.manage.includes(role);

  useEffect(() => {
    A.templates().then((t) => {
      setTemplates(t);
      if (t.length) setTpl(t[0].id);
    });
  }, []);

  return (
    <div className="panel grow">
      <h2>Scenarios</h2>
      <div className="scroll" style={{ flex: 1 }}>
        {scenarios.length === 0 && <div className="empty">No scenarios yet.</div>}
        {scenarios.map((s) => (
          <div key={s.id} className={`scenario-item ${s.id === selectedId ? "active" : ""}`}
            onClick={() => onSelect(s.id)}>
            <div className="row">
              <span className="name">{s.name}</span>
              <span className="spacer" style={{ flex: 1 }} />
              <span className={`status-tag status-${s.status}`}>{s.status}</span>
            </div>
            <div className="meta">#{s.id} · {s.template} · by {s.created_by}</div>
          </div>
        ))}
      </div>
      {canManage && (
        <div style={{ marginTop: 10, borderTop: "1px solid var(--border)", paddingTop: 10 }}>
          <div className="field">
            <label>New exercise from template</label>
            <select value={tpl} onChange={(e) => setTpl(e.target.value)}>
              {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </div>
          <div className="field">
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="exercise name (optional)" />
          </div>
          <button className="primary" style={{ width: "100%" }}
            onClick={async () => { await onCreate(tpl, name); setName(""); }}>
            + Create scenario
          </button>
        </div>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
function EventPanel({ scenario, nodes, onInject, role }) {
  const [catalog, setCatalog] = useState([]);
  const [type, setType] = useState("ransomware");
  const [title, setTitle] = useState("");
  const [target, setTarget] = useState("");
  const [err, setErr] = useState("");
  const canManage = CAN.manage.includes(role);

  useEffect(() => { A.eventCatalog().then(setCatalog); }, []);
  useEffect(() => { if (nodes.length && !target) setTarget(nodes[0].id); }, [nodes]);

  if (!canManage) return null;
  const running = scenario?.status === "running";

  const inject = async () => {
    setErr("");
    try {
      const ev = await A.createEvent(scenario.id, {
        type, title: title || `${type} on ${target}`, target_node: target,
      });
      await A.injectEvent(ev.id);
      setTitle("");
      onInject();
    } catch (ex) { setErr(ex.message); }
  };

  return (
    <div className="panel">
      <h2>Inject Event {!running && <span style={{ color: "var(--warn)" }}>(deploy first)</span>}</h2>
      <div className="field">
        <label>Attack type (dummy)</label>
        <select value={type} onChange={(e) => setType(e.target.value)}>
          {catalog.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>
      <div className="field">
        <label>Target node</label>
        <select value={target} onChange={(e) => setTarget(e.target.value)}>
          {nodes.map((n) => <option key={n.id} value={n.id}>{n.id} ({n.role})</option>)}
        </select>
      </div>
      <div className="field">
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="event title (optional)" />
      </div>
      <button className="primary" disabled={!running} onClick={inject}>⚡ Inject now</button>
      <div className="err">{err}</div>
    </div>
  );
}

// --------------------------------------------------------------------------- //
function IncidentPanel({ scoreboard, role, onAdvance }) {
  const canRespond = CAN.respond.includes(role);
  const rows = scoreboard?.incidents || [];
  const ACTIONS = [
    ["detected", "detect", "detected_at"],
    ["triaged", "triage", "triaged_at"],
    ["contained", "contain", "contained_at"],
    ["recovered", "recover", "recovered_at"],
  ];
  const nextAction = (status) => {
    const order = ["open", "detected", "triaged", "contained", "recovered"];
    const idx = order.indexOf(status);
    const map = { open: "detect", detected: "triage", triaged: "contain", contained: "recover" };
    return map[status];
  };

  return (
    <div className="panel grow">
      <h2>Incidents &amp; Scoring · avg {scoreboard?.average_score ?? 0}/100</h2>
      <div className="scroll" style={{ flex: 1 }}>
        {rows.length === 0 && <div className="empty">No incidents. Inject an event to start scoring.</div>}
        {rows.map((inc) => {
          const na = nextAction(inc.status);
          return (
            <div key={inc.id} className="incident">
              <div className="row">
                <span className="title">{inc.title}</span>
                <span style={{ flex: 1 }} />
                <span className="score-badge">{inc.score ?? 0}</span>
              </div>
              <div className="metrics">
                {["TTD", "TTT", "TTC", "TTR"].map((k) => {
                  const v = inc.metrics[k];
                  const met = v != null && v <= TARGETS[k];
                  return (
                    <div key={k} className={`metric ${v == null ? "" : met ? "met" : "missed"}`}>
                      <div className="k">{k}</div>
                      <div className="v">{fmt(v)}</div>
                    </div>
                  );
                })}
              </div>
              <div className="row">
                <span className={`status-tag status-running`}>{inc.status}</span>
                <span style={{ flex: 1 }} />
                {canRespond && na && (
                  <button className="primary" onClick={() => onAdvance(inc.id, na)}>
                    {na} ▶
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- //
function LogFeed({ logs }) {
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [logs]);
  return (
    <div className="panel grow">
      <h2>SOC / SIEM Live Feed</h2>
      <div className="scroll" ref={ref} style={{ flex: 1 }}>
        {logs.length === 0 && <div className="empty">No logs yet.</div>}
        {logs.map((l, i) => (
          <div key={i} className={`log-line sev-${l.severity}`}>
            <span className="log-src">{l.source}</span>
            <span className="log-msg">{l.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- //
function ContainmentPanel({ nodes, role, onAction }) {
  if (!CAN.respond.includes(role)) return null;
  const actionable = nodes.filter((n) =>
    ["compromised", "quarantined"].includes(n.status));
  return (
    <div className="panel">
      <h2>Containment</h2>
      {actionable.length === 0 && (
        <div className="empty">No compromised hosts. Nothing to contain.</div>
      )}
      {actionable.map((n) => (
        <div key={n.id} className="row" style={{ padding: "5px 0", borderBottom: "1px solid #182230" }}>
          <span style={{ fontWeight: 600 }}>{n.id}</span>
          <span className={`status-tag status-${n.status === "compromised" ? "halted" : "destroyed"}`}
            style={{ marginLeft: 8 }}>{n.status}</span>
          <span style={{ flex: 1 }} />
          {n.status === "compromised" ? (
            <button onClick={() => onAction(n.id, "quarantine")}>Quarantine ▶</button>
          ) : (
            <button className="primary" onClick={() => onAction(n.id, "restore")}>Restore ▶</button>
          )}
        </div>
      ))}
    </div>
  );
}

// --------------------------------------------------------------------------- //
function Dashboard({ onLogout }) {
  const role = getRole();
  const user = getUsername();
  const [scenarios, setScenarios] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [scenario, setScenario] = useState(null);
  const [topology, setTopology] = useState({ nodes: [], edges: [] });
  const [logs, setLogs] = useState([]);
  const [scoreboard, setScoreboard] = useState({ incidents: [], average_score: 0 });
  const [guardrails, setGuardrails] = useState({});
  const [toast, setToast] = useState("");
  const [err, setErr] = useState("");
  const wsRef = useRef(null);

  const canManage = CAN.manage.includes(role);

  const loadScenarios = useCallback(() => A.scenarios().then(setScenarios), []);
  const loadGuardrails = useCallback(() => A.guardrails().then(setGuardrails), []);

  useEffect(() => { loadScenarios(); loadGuardrails(); }, []);

  const showToast = (m) => { setToast(m); setTimeout(() => setToast(""), 3500); };

  const refreshScenario = useCallback(async (id) => {
    const [sc, topo, lg, sb] = await Promise.all([
      A.scenario(id), A.topology(id), A.logs(id), A.scoreboard(id),
    ]);
    setScenario(sc); setTopology(topo); setLogs(lg); setScoreboard(sb);
  }, []);

  // Select scenario → load + open WS
  useEffect(() => {
    if (!selectedId) return;
    refreshScenario(selectedId);
    if (wsRef.current) wsRef.current.close();
    wsRef.current = openFeed(selectedId, (msg) => {
      if (msg.kind === "log") setLogs((prev) => [...prev.slice(-250), msg.data]);
      else if (msg.kind === "topology") setTopology(msg.data);
      else if (msg.kind === "event") {
        showToast(`⚡ Event injected: ${msg.data.title}`);
        A.scoreboard(selectedId).then(setScoreboard);
      } else if (msg.kind === "incident") A.scoreboard(selectedId).then(setScoreboard);
      else if (msg.kind === "status") setScenario((s) => s ? { ...s, status: msg.data.status } : s);
      else if (msg.kind === "killswitch") {
        showToast("🛑 KILL SWITCH ENGAGED — all VMs halted");
        loadGuardrails(); A.scenario(selectedId).then(setScenario);
      }
    });
    return () => wsRef.current && wsRef.current.close();
  }, [selectedId]);

  const wrap = (fn) => async (...args) => {
    setErr("");
    try { return await fn(...args); }
    catch (ex) { setErr(ex.message); showToast("⚠ " + ex.message); }
  };

  const createScenario = wrap(async (tpl, name) => {
    const sc = await A.createScenario(tpl, name);
    await loadScenarios();
    setSelectedId(sc.id);
  });
  const deploy = wrap(async () => { await A.deploy(selectedId); await refreshScenario(selectedId); await loadScenarios(); });
  const destroy = wrap(async () => { await A.destroy(selectedId); await refreshScenario(selectedId); await loadScenarios(); });
  const advance = wrap(async (incId, action) => { await A.advance(incId, action); await A.scoreboard(selectedId).then(setScoreboard); });
  const doNodeAction = wrap(async (node, action) => {
    await A.nodeAction(selectedId, node, action);
    await refreshScenario(selectedId);
  });
  const killSwitch = wrap(async () => {
    const next = !guardrails.kill_switch;
    await A.killSwitch(next);
    await loadGuardrails();
    if (selectedId) { await refreshScenario(selectedId); await loadScenarios(); }
  });

  const running = scenario?.status === "running";

  return (
    <>
      <div className="topbar">
        <h1>🛡️ CYBER SIMULATOR</h1>
        <span className={`pill ${guardrails.isolation_enforced ? "on" : "off"}`}>
          {guardrails.isolation_enforced ? "ISOLATED ✓" : "ISOLATION OFF"}
        </span>
        <span className={`pill ${guardrails.kill_switch ? "off" : "on"}`}>
          {guardrails.kill_switch ? "KILL SWITCH ON" : "SYSTEMS NOMINAL"}
        </span>
        <span className="spacer" style={{ flex: 1 }} />
        <span className="role-badge">{user} · {role}</span>
        {CAN.manage.includes(role) && (
          <button className="danger" onClick={killSwitch}>
            {guardrails.kill_switch ? "Release Kill Switch" : "🛑 KILL SWITCH"}
          </button>
        )}
        <button className="ghost" onClick={onLogout}>Logout</button>
      </div>

      <div className="layout">
        <div className="col">
          <ScenarioColumn scenarios={scenarios} selectedId={selectedId}
            onSelect={setSelectedId} onCreate={createScenario} role={role} reload={loadScenarios} />
        </div>

        <div className="col">
          <div className="panel" style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
            <div>
              <div style={{ fontWeight: 600 }}>{scenario ? scenario.name : "No scenario selected"}</div>
              <div style={{ fontSize: 11, color: "var(--muted)" }}>
                {scenario ? `${scenario.template} · ${scenario.status}` : "Pick or create a scenario"}
              </div>
            </div>
            <span style={{ flex: 1 }} />
            {canManage && scenario && (
              <>
                <button className="primary" disabled={running || scenario.status === "destroyed"} onClick={deploy}>Deploy</button>
                <button disabled={!running} onClick={destroy}>Destroy</button>
              </>
            )}
            {scenario && <a href={A.aarUrl(scenario.id)} target="_blank" rel="noreferrer"><button className="ghost">AAR ↓</button></a>}
          </div>
          <div className="panel grow">
            <h2>Live Topology</h2>
            <div style={{ flex: 1, minHeight: 0 }}><TopologyGraph topology={topology} /></div>
          </div>
          <LogFeed logs={logs} />
        </div>

        <div className="col">
          {scenario && <EventPanel scenario={scenario} nodes={topology.nodes} onInject={() => refreshScenario(selectedId)} role={role} />}
          <ContainmentPanel nodes={topology.nodes} role={role} onAction={doNodeAction} />
          <IncidentPanel scoreboard={scoreboard} role={role} onAdvance={advance} />
        </div>
      </div>
      {toast && <div className="toast">{toast}</div>}
    </>
  );
}

// --------------------------------------------------------------------------- //
export default function App() {
  const [authed, setAuthed] = useState(!!getToken());
  if (!authed) return <Login onDone={() => setAuthed(true)} />;
  const onLogout = () => { logout(); setAuthed(false); };
  if (getRole() === "Commander") return <CommanderView onLogout={onLogout} />;
  return <Dashboard onLogout={onLogout} />;
}
