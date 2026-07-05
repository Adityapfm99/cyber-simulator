// Topology view: circular default layout, but every node can be dragged
// individually. Canvas also supports mouse-wheel zoom and background drag-pan.
import React, { useEffect, useRef, useState, useCallback } from "react";

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

const W = 560;
const H = 460;
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

export default function TopologyGraph({ topology }) {
  const nodes = topology?.nodes || [];
  const edges = topology?.edges || [];
  const cx = W / 2;
  const cy = H / 2;
  const R = Math.min(W, H) / 2 - 70;

  const svgRef = useRef(null);
  const dragRef = useRef(null); // {type:'node',id,offX,offY} | {type:'pan',sx,sy,vx,vy}
  const [view, setView] = useState({ scale: 1, x: 0, y: 0 });
  const [overrides, setOverrides] = useState({}); // nodeId -> {x,y}

  // Default circular layout.
  const defaults = {};
  nodes.forEach((n, i) => {
    const angle = (2 * Math.PI * i) / Math.max(nodes.length, 1) - Math.PI / 2;
    defaults[n.id] = { x: cx + R * Math.cos(angle), y: cy + R * Math.sin(angle) };
  });
  const posOf = (id) => overrides[id] || defaults[id];

  // Screen px -> viewBox coords.
  const toSvg = useCallback((clientX, clientY) => {
    const r = svgRef.current.getBoundingClientRect();
    return { x: ((clientX - r.left) / r.width) * W, y: ((clientY - r.top) / r.height) * H };
  }, []);
  // Screen px -> world coords (undo the pan/zoom transform).
  const toWorld = useCallback((clientX, clientY) => {
    const s = toSvg(clientX, clientY);
    return { x: (s.x - view.x) / view.scale, y: (s.y - view.y) / view.scale };
  }, [toSvg, view]);

  // Non-passive wheel = zoom toward cursor.
  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    const onWheel = (e) => {
      e.preventDefault();
      const p = toSvg(e.clientX, e.clientY);
      setView((v) => {
        const scale = clamp(v.scale * (e.deltaY < 0 ? 1.12 : 0.893), 0.4, 5);
        const k = scale / v.scale;
        return { scale, x: p.x - (p.x - v.x) * k, y: p.y - (p.y - v.y) * k };
      });
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [toSvg]);

  const startNodeDrag = (e, id) => {
    e.stopPropagation();
    const w = toWorld(e.clientX, e.clientY);
    const p = posOf(id);
    dragRef.current = { type: "node", id, offX: w.x - p.x, offY: w.y - p.y };
  };
  const startPan = (e) => {
    dragRef.current = { type: "pan", sx: e.clientX, sy: e.clientY, vx: view.x, vy: view.y };
  };
  const onMouseMove = (e) => {
    const d = dragRef.current;
    if (!d) return;
    if (d.type === "node") {
      const w = toWorld(e.clientX, e.clientY);
      setOverrides((o) => ({ ...o, [d.id]: { x: w.x - d.offX, y: w.y - d.offY } }));
    } else {
      const r = svgRef.current.getBoundingClientRect();
      const dx = ((e.clientX - d.sx) / r.width) * W;
      const dy = ((e.clientY - d.sy) / r.height) * H;
      setView((v) => ({ ...v, x: d.vx + dx, y: d.vy + dy }));
    }
  };
  const endDrag = () => { dragRef.current = null; };
  const resetView = () => setView({ scale: 1, x: 0, y: 0 });
  const resetLayout = () => { setOverrides({}); resetView(); };

  if (!nodes.length) {
    return <div className="empty">No topology deployed. Deploy a scenario to instantiate the lab.</div>;
  }

  return (
    <div style={{ position: "relative", width: "100%", height: "100%" }}>
      <div style={{ position: "absolute", top: 6, right: 6, zIndex: 2, display: "flex", gap: 4 }}>
        <button className="ghost" style={{ padding: "3px 8px", fontSize: 14, lineHeight: 1 }}
          title="Zoom in" onClick={() => setView((v) => ({ ...v, scale: clamp(v.scale * 1.2, 0.4, 5) }))}>＋</button>
        <button className="ghost" style={{ padding: "3px 8px", fontSize: 14, lineHeight: 1 }}
          title="Zoom out" onClick={() => setView((v) => ({ ...v, scale: clamp(v.scale * 0.83, 0.4, 5) }))}>－</button>
        <button className="ghost" style={{ padding: "3px 8px", fontSize: 11 }}
          title="Reset layout & view" onClick={resetLayout}>reset</button>
      </div>
      <div style={{ position: "absolute", bottom: 6, left: 8, zIndex: 2, fontSize: 10, color: "var(--muted)" }}>
        drag node = move · scroll = zoom · drag background = pan · {Math.round(view.scale * 100)}%
      </div>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        width="100%" height="100%"
        style={{ maxHeight: "100%", cursor: "grab", touchAction: "none" }}
        onMouseDown={startPan}
        onMouseMove={onMouseMove}
        onMouseUp={endDrag}
        onMouseLeave={endDrag}
      >
        <g transform={`translate(${view.x} ${view.y}) scale(${view.scale})`}>
          {edges.map((e, i) => {
            const a = posOf(e.src);
            const b = posOf(e.dst);
            if (!a || !b) return null;
            return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#26374a" strokeWidth="1.5" />;
          })}
          {nodes.map((n) => {
            const p = posOf(n.id);
            const color = STATUS_COLOR[n.status] || "#7d8ea1";
            const icon = KIND_ICON[n.kind] || (n.role === "firewall" ? "🛡️" : "🖥️");
            const compromised = n.status === "compromised";
            return (
              <g key={n.id} onMouseDown={(e) => startNodeDrag(e, n.id)} style={{ cursor: "grab" }}>
                <circle cx={p.x} cy={p.y} r={compromised ? 24 : 20} fill="#121821" stroke={color}
                  strokeWidth={compromised ? 3 : 2}>
                  {compromised && (
                    <animate attributeName="r" values="20;26;20" dur="1.2s" repeatCount="indefinite" />
                  )}
                </circle>
                <text x={p.x} y={p.y + 5} textAnchor="middle" fontSize="16" style={{ pointerEvents: "none" }}>{icon}</text>
                <text x={p.x} y={p.y + 36} textAnchor="middle" fontSize="10" fill="#d7e0ea" style={{ pointerEvents: "none" }}>{n.id}</text>
                <text x={p.x} y={p.y + 48} textAnchor="middle" fontSize="8" fill={color} style={{ pointerEvents: "none" }}>{n.status}</text>
              </g>
            );
          })}
        </g>
      </svg>
    </div>
  );
}
