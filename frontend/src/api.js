// Thin API client. Token is kept in localStorage.
const BASE = "/api";

export function getToken() {
  return localStorage.getItem("cybersim_token");
}
export function getRole() {
  return localStorage.getItem("cybersim_role");
}
export function getUsername() {
  return localStorage.getItem("cybersim_user");
}

function authHeaders(extra = {}) {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}`, ...extra } : extra;
}

async function handle(res) {
  if (res.status === 401) {
    logout();
    throw new Error("Session expired — please log in again.");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {}
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  const ct = res.headers.get("content-type") || "";
  return ct.includes("application/json") ? res.json() : res;
}

export async function login(username, password) {
  const body = new URLSearchParams({ username, password });
  const res = await fetch(`${BASE}/auth/login`, { method: "POST", body });
  const data = await handle(res);
  localStorage.setItem("cybersim_token", data.access_token);
  localStorage.setItem("cybersim_role", data.role);
  localStorage.setItem("cybersim_user", data.username);
  return data;
}

export function logout() {
  localStorage.removeItem("cybersim_token");
  localStorage.removeItem("cybersim_role");
  localStorage.removeItem("cybersim_user");
}

export const api = {
  get: (path) => fetch(`${BASE}${path}`, { headers: authHeaders() }).then(handle),
  post: (path, body) =>
    fetch(`${BASE}${path}`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: body === undefined ? undefined : JSON.stringify(body),
    }).then(handle),
};

// Endpoint helpers
export const A = {
  templates: () => api.get("/scenarios/templates"),
  scenarios: () => api.get("/scenarios"),
  createScenario: (template, name) => api.post("/scenarios", { template, name }),
  scenario: (id) => api.get(`/scenarios/${id}`),
  deploy: (id) => api.post(`/scenarios/${id}/deploy`),
  destroy: (id) => api.post(`/scenarios/${id}/destroy`),
  topology: (id) => api.get(`/scenarios/${id}/topology`),
  events: (id) => api.get(`/scenarios/${id}/events`),
  eventCatalog: () => api.get("/events/catalog"),
  createEvent: (id, ev) => api.post(`/scenarios/${id}/events`, ev),
  injectEvent: (eid) => api.post(`/events/${eid}/inject`),
  logs: (id, limit = 150) => api.get(`/scenarios/${id}/logs?limit=${limit}`),
  scoreboard: (id) => api.get(`/scenarios/${id}/scoreboard`),
  advance: (incId, action) => api.post(`/incidents/${incId}/advance?action=${action}`),
  defend: (incId, action, target = "") =>
    api.post(`/incidents/${incId}/defend?action=${action}${target ? `&target=${encodeURIComponent(target)}` : ""}`),
  nodeAction: (id, node, action) =>
    api.post(`/scenarios/${id}/nodes/${encodeURIComponent(node)}/action?action=${action}`),
  c2: (id) => api.get(`/scenarios/${id}/c2`),
  ot: (id) => api.get(`/scenarios/${id}/ot`),
  // MOD-02 Web Security Lab
  websecRegistry: () => api.get("/lab/websec/registry"),
  websecPatch: (vuln, patched) => api.post(`/lab/websec/patch?vuln=${vuln}&patched=${patched}`),
  websecExploit: (vuln) => {
    switch (vuln) {
      case "sqli": return api.post("/lab/websec/login", { username: "admin'--", password: "x" });
      case "xss": return api.get(`/lab/websec/search?q=${encodeURIComponent("<script>alert(1)</script>")}`);
      case "idor": return api.get("/lab/websec/invoice/3?as_user=trainee-01");
      case "cmdi": return api.get(`/lab/websec/ping?host=${encodeURIComponent("127.0.0.1;id")}`);
      case "exposure": return api.get("/lab/websec/debug");
      default: return Promise.reject(new Error("unknown vuln"));
    }
  },

  guardrails: () => api.get("/admin/guardrails"),
  killSwitch: (value) => api.post("/admin/kill-switch", { value }),
  audit: (limit = 100) => api.get(`/admin/audit?limit=${limit}`),
  auditVerify: () => api.get("/admin/audit/verify"),
  aarUrl: (id) => `${BASE}/scenarios/${id}/aar.pdf`,
};

// The UI polls (see the dashboards) rather than holding a WebSocket, so it works
// on serverless hosts such as Vercel that do not support long-lived sockets.
