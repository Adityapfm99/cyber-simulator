// Deterministic force-free topology layout: nodes on a circle, edges as lines.
import React from "react";

const STATUS_COLOR = {
  up: "#35d0a5",
  compromised: "#ff5c5c",
  quarantined: "#f5a623",
  halted: "#7d8ea1",
  destroyed: "#40506080",
  provisioning: "#4aa3ff",
};

const KIND_ICON = {
  firewall: "🛡️",
  siem: "📊",
  ot: "⚙️",
  c2: "📡",
  vendor: "📦",
};

export default function TopologyGraph({ topology }) {
  const nodes = topology?.nodes || [];
  const edges = topology?.edges || [];
  const W = 560;
  const H = 460;
  const cx = W / 2;
  const cy = H / 2;
  const R = Math.min(W, H) / 2 - 70;

  const pos = {};
  nodes.forEach((n, i) => {
    const angle = (2 * Math.PI * i) / Math.max(nodes.length, 1) - Math.PI / 2;
    pos[n.id] = { x: cx + R * Math.cos(angle), y: cy + R * Math.sin(angle) };
  });

  if (!nodes.length) {
    return <div className="empty">No topology deployed. Deploy a scenario to instantiate the lab.</div>;
  }

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="100%" style={{ maxHeight: "100%" }}>
      {edges.map((e, i) => {
        const a = pos[e.src];
        const b = pos[e.dst];
        if (!a || !b) return null;
        return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#26374a" strokeWidth="1.5" />;
      })}
      {nodes.map((n) => {
        const p = pos[n.id];
        const color = STATUS_COLOR[n.status] || "#7d8ea1";
        const icon = KIND_ICON[n.kind] || (n.role === "firewall" ? "🛡️" : "🖥️");
        const compromised = n.status === "compromised";
        return (
          <g key={n.id}>
            <circle cx={p.x} cy={p.y} r={compromised ? 24 : 20} fill="#121821" stroke={color}
              strokeWidth={compromised ? 3 : 2}>
              {compromised && (
                <animate attributeName="r" values="20;26;20" dur="1.2s" repeatCount="indefinite" />
              )}
            </circle>
            <text x={p.x} y={p.y + 5} textAnchor="middle" fontSize="16">{icon}</text>
            <text x={p.x} y={p.y + 36} textAnchor="middle" fontSize="10" fill="#d7e0ea">{n.id}</text>
            <text x={p.x} y={p.y + 48} textAnchor="middle" fontSize="8" fill={color}>{n.status}</text>
          </g>
        );
      })}
    </svg>
  );
}
