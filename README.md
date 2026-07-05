# Cyber Simulator — Defensive Cyber-Range Training Platform

A software MVP of a self-hosted, **air-gapped cyber-range** for training defensive
security teams (blue teams). It is built from a *Spesifikasi Teknis (Spektek)* —
a technical requirements document for a defensive cyber simulator intended for a
government / military institution, where **data sovereignty and safety guardrails**
are the overriding concerns.

This repository implements the **software** portions of that spec (Sections 2–4).
The hardware & network infrastructure (Section 1) cannot be expressed in code and
is captured as documentation instead.

> ⚠️ **Training only — everything is a harmless dummy.** The platform never handles
> real malware, real personnel identities, real credentials, or real network maps.
> The safety guardrails in Section 4 are enforced *in code*, not by policy — see
> [Security guardrails](#security-guardrails-§4).

---

## Table of contents
- [What it does](#what-it-does)
- [Architecture](#architecture)
- [Quick start](#quick-start)
- [Demo walkthrough](#demo-walkthrough)
- [Roles (RBAC)](#roles-rbac)
- [Security guardrails (§4)](#security-guardrails-§4)
- [Project layout](#project-layout)
- [API overview](#api-overview)

---

## What it does

The platform runs a **training exercise**: an Exercise Director spins up a simulated
lab, injects cyber-attacks into it, and a SOC Analyst races to detect and respond
while the system scores their performance and produces an After-Action Review.

| Spektek section | Feature | Status |
|---|---|---|
| §2 Exercise Director | Multi-scenario dashboard, live topology, event injection | ✅ |
| §2 Scenario Engine | Deploy/destroy a simulated lab (Infrastructure-as-Code style), dummy background traffic | ✅ |
| §2 Scoring & AAR | Captures TTD / TTT / TTC / TTR, exports a PDF After-Action Review | ✅ |
| §3 SOC Simulator | SIEM emulator streaming fake Firewall / EDR / DNS / Proxy logs | ✅ |
| §3 Attack scenarios | Dummy ransomware, OT fault, port-scan, exfil, supply-chain anomaly, … | ✅ |
| §4 Kill Switch | One control that instantly halts every training VM | ✅ |
| §4 Dummy-Data Enforcement | Allowlist validation — private IPs only, dummy identities, secret scanning | ✅ |
| §4 RBAC + Immutable Audit | 5 separated roles + a hash-chained, tamper-evident audit log | ✅ |
| §1 Hardware / Network | Documentation only (see `docs/`) | 📄 |

**Not yet built** (candidate next slices): Commander C2-resilience dashboard,
Web Security Lab (real vulnerable containers), OT/ICS gauge failure animation,
automated test suite.

---

## Architecture

```
┌──────────────────────────┐         REST + WebSocket        ┌───────────────────────────┐
│   React dashboard (Vite)  │  ◀──────────────────────────▶  │   FastAPI backend          │
│   Exercise Director UI    │   /api proxy · /ws live feed    │   simulation engine         │
└──────────────────────────┘                                 │   + §4 guardrails           │
                                                             └────────────┬──────────────┘
                                                                          │
                                                                 SQLite (SQLModel)
```

- **Backend** — Python / FastAPI + SQLModel (SQLite). A background ticker emits
  baseline SOC traffic every ~2s and fires scheduled events. Live updates are
  pushed to the UI over a WebSocket.
- **Frontend** — React (Vite). Talks to the backend through Vite's dev proxy
  (`/api` → `:8000`, `/ws` → WebSocket), so there is no CORS friction in dev.
- **No external services.** Password hashing (PBKDF2) and auth tokens (HMAC) use
  only the Python standard library — nothing to phone home, which suits an
  air-gapped deployment.

---

## Quick start

You need **Python 3.10+** (via [`uv`](https://github.com/astral-sh/uv)) and **Node 18+**.

### 1. Backend
```bash
cd backend
uv sync                        # install dependencies into .venv
uv run python -m app.seed      # create the SQLite DB + seed the 5 demo users
uv run uvicorn app.main:app --reload --port 8000
```
- API + interactive docs: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>

### 2. Frontend (separate terminal)
```bash
cd frontend
npm install
npm run dev
```
- Dashboard: <http://localhost:5173>

### 3. Log in
Open the dashboard and sign in with any [demo account](#roles-rbac) — start with
`director` / `director123`.

---

## Demo walkthrough

1. **Sign in as `director`.** Create a scenario from the *Enterprise SOC Defense*
   template, then click **Deploy** — the topology instantiates (8 nodes) and the
   SOC live feed starts streaming baseline logs.
2. **Inject an attack.** In the *Inject Event* panel pick `ransomware`, target
   `workstation-01`, and click **Inject now**. The target node pulses red on the
   topology, critical logs appear in the feed, and an **incident opens** (its
   response clock starts).
3. **Respond as `analyst`.** Log in as `analyst` / `analyst123` in another browser.
   Work the incident through **detect → triage → contain → recover**. Each step
   stamps a time (TTD/TTT/TTC/TTR) and the score climbs toward 100.
4. **Review.** Click **AAR ↓** to download the PDF After-Action Review — incident
   timeline, response times vs. targets, and an SOP gap analysis.
5. **Emergency stop.** As `director` or `admin`, hit **🛑 KILL SWITCH** — every
   VM halts immediately and all activity stops until it is released.

---

## Roles (RBAC)

Duties are separated across five roles (§4). Seeded demo accounts:

| Role | Username | Password | Can do |
|---|---|---|---|
| **Admin** | `admin` | `admin123` | Everything, including isolation config |
| **Exercise Director** | `director` | `director123` | Build/run scenarios, inject events, kill switch |
| **Commander** | `commander` | `commander123` | Leadership view (C2 dashboard — *in progress*) |
| **SOC Analyst** | `analyst` | `analyst123` | Detect / triage / contain / recover incidents |
| **Observer** | `observer` | `observer123` | Read-only |

> Change these before any non-demo use. Passwords are for the local training demo only.

---

## Security guardrails (§4)

These are enforced in `backend/app/guardrails.py` and rejected with HTTP 422:

- **Strict isolation** — only private RFC1918 / documentation IP ranges may appear
  in a lab topology. A public/routable address (which would imply a real network
  map or internet routing) is refused.
- **Dummy-data enforcement** — scenario identities must be on a dummy allowlist;
  payloads are scanned for anything resembling a real credential (private keys,
  API keys, JWTs); "attacks" must be one of a fixed allowlist of harmless dummy
  event types (there is no path to run real malware).
- **Kill switch** — a single control halts every running VM and blocks all event
  injection until released.
- **Immutable audit log** — every meaningful action is written to a hash-chained
  log (`hash = sha256(prev_hash + row)`). Tampering with or deleting any row
  breaks the chain; `GET /admin/audit/verify` re-hashes the whole chain and
  reports the first break.

---

## Project layout

```
cyber-simulator/
├── backend/
│   ├── app/
│   │   ├── main.py         FastAPI app + background simulation ticker
│   │   ├── routes.py       REST + WebSocket API
│   │   ├── models.py       SQLModel tables (users, scenarios, nodes, events, logs, incidents, audit)
│   │   ├── auth.py         PBKDF2 passwords, HMAC tokens, RBAC dependencies
│   │   ├── guardrails.py   §4 safety enforcement (isolation, dummy-data, kill switch)
│   │   ├── audit.py        hash-chained tamper-evident audit log
│   │   ├── scenarios.py    §2 scenario engine (deploy/destroy, topology)
│   │   ├── events.py       §2 event injection / §3 attack logic
│   │   ├── soc.py          §3 SIEM log emitter (baseline + attack)
│   │   ├── scoring.py      §2 TTD/TTT/TTC/TTR metrics + scoring
│   │   ├── aar.py          §2 After-Action Review (PDF via reportlab, HTML fallback)
│   │   ├── realtime.py     WebSocket broadcast hub
│   │   └── seed.py         demo users
│   └── scenario_templates/ *.yaml lab definitions (enterprise SOC, OT/ICS base)
└── frontend/
    └── src/
        ├── App.jsx         dashboard: scenarios, topology, feed, events, scoring
        ├── TopologyGraph.jsx  SVG network diagram
        ├── api.js          API client + WebSocket helper
        └── styles.css
```

---

## API overview

Full interactive documentation is at `/docs` when the backend is running. Key routes:

| Method | Path | Role | Purpose |
|---|---|---|---|
| POST | `/auth/login` | any | Obtain a bearer token |
| GET | `/scenarios/templates` | any | List lab templates |
| POST | `/scenarios` | Admin, Director | Create a scenario |
| POST | `/scenarios/{id}/deploy` | Admin, Director | Instantiate the lab (guardrail-checked) |
| POST | `/scenarios/{id}/destroy` | Admin, Director | Tear down the lab |
| GET | `/scenarios/{id}/topology` | any | Nodes + edges |
| POST | `/scenarios/{id}/events` | Admin, Director | Create an event (dummy-type validated) |
| POST | `/events/{id}/inject` | Admin, Director | Fire an event now |
| POST | `/incidents/{id}/advance?action=` | Admin, Analyst | detect / triage / contain / recover |
| GET | `/scenarios/{id}/scoreboard` | any | Incidents + scores |
| GET | `/scenarios/{id}/aar.pdf` | any | Download the After-Action Review |
| POST | `/admin/kill-switch` | Admin, Director | Engage / release the kill switch |
| GET | `/admin/audit` · `/admin/audit/verify` | Admin, Director | Read / verify the audit chain |
| WS | `/ws/scenarios/{id}` | — | Live feed: logs, events, topology, incidents |
