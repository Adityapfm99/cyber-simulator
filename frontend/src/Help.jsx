// In-app guide: how to add a scenario and how to run/test an exercise.
import React from "react";

export default function Help({ open, onClose }) {
  if (!open) return null;
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="row">
          <h2 style={{ margin: 0 }}>📖 How to use the Cyber Range</h2>
          <span style={{ flex: 1 }} />
          <button className="ghost" onClick={onClose}>✕ Close</button>
        </div>

        <div className="guide-section">
          <h3>1 · Add a scenario <span className="role-note">Admin / Exercise Director</span></h3>
          <ol>
            <li>In the left <b>Scenarios</b> column, pick a template from the dropdown
              (e.g. <i>Enterprise SOC Defense</i> or <i>OT/ICS Base</i>).</li>
            <li>Optionally type an exercise name, then click <b>+ Create scenario</b>.</li>
            <li>Select it in the list, then click <b>Deploy</b> in the top bar of the
              centre panel. The topology instantiates and the SOC feed starts streaming.</li>
          </ol>
          <p style={{ fontSize: 12, color: "var(--muted)", margin: "4px 0 0" }}>
            💡 <b>Live Topology</b>: drag a node to move it, scroll to zoom, drag the
            background to pan, and use <b>reset</b> to restore the layout.
          </p>
        </div>

        <div className="guide-section">
          <h3>2 · Run &amp; test an exercise</h3>
          <ol>
            <li><b>Inject an attack</b> (Director): in the <b>Inject Event</b> panel, choose a
              dummy attack type (e.g. <code>ransomware</code>), pick a target node, and click
              <b> ⚡ Inject now</b>. The target turns red and critical logs appear.</li>
            <li><b>Detect &amp; respond</b> (SOC Analyst): open the <b>Incidents</b> panel and
              step the incident through <b>detect → triage → contain → recover</b>. Each step
              records a response time (TTD/TTT/TTC/TTR) and raises the score.</li>
            <li><b>Contain the host</b> (SOC Analyst): in the <b>Containment</b> panel,
              <b> Quarantine</b> a compromised node then <b>Restore</b> it — these actions
              also drive the incident to contained / recovered.</li>
            <li><b>Review</b>: click <b>AAR ↓</b> to download the After-Action Review PDF
              (timeline, response times vs. targets, SOP gaps).</li>
          </ol>
        </div>

        <div className="guide-section">
          <h3>3 · Incidents &amp; Scoring <span className="role-note">what "avg 0/100" means</span></h3>
          <p style={{ fontSize: 12.5, margin: "0 0 6px" }}>
            Every injected attack opens an <b>incident</b>. The platform scores how fast the
            blue team responds, from <b>0 to 100</b> — 25 points for each phase completed
            within its target time:
          </p>
          <ul>
            <li><b>TTD</b> Time to Detect · <b>TTT</b> Time to Triage · <b>TTC</b> Time to
              Contain · <b>TTR</b> Time to Recover (25 pts each).</li>
            <li><b>avg 0/100</b> just means the incident isn't responded to yet — normal for a
              fresh attack. "No incidents" means that scenario hasn't been attacked.</li>
            <li><b>Raise the score</b> (SOC Analyst): in the <b>Incidents</b> panel click
              <b> detect → triage → contain → recover</b> (25 → 50 → 75 → 100), or use the
              <b> Containment</b> panel (Quarantine → Restore) which auto-contains and recovers.</li>
            <li>The final scores feed the <b>AAR</b> report as the team's performance measure.</li>
          </ul>
        </div>

        <div className="guide-section">
          <h3>4 · Training modules <span className="role-note">top bar buttons</span></h3>
          <ul>
            <li><b>🕸 Web Sec Lab</b> (MOD-02): a deliberately-vulnerable web app (OWASP
              Top 10 — SQLi, XSS, IDOR, command injection, data exposure), all sandboxed
              dummy data. Click <b>Uji exploit / Test exploit</b> to see each flaw, then
              <b> Patch</b> it (SOC Analyst) — the hardening score rises as you secure them.</li>
            <li><b>🏭 OT/ICS HMI</b> (MOD-03): a SCADA/HMI digital twin with live power &amp;
              HVAC gauges. Select an <i>OT/ICS Base</i> scenario, inject <code>ot_fault</code>,
              then open this to watch the gauges go <b>red / alarm</b> (overvoltage, cooling
              failure). <b>Restore</b> the OT node to bring them back to green.</li>
            <li><b>SOC Simulator</b> (MOD-01): the live SOC/SIEM feed in the centre panel.</li>
          </ul>
        </div>

        <div className="guide-section">
          <h3>5 · Commander &amp; safety</h3>
          <ul>
            <li><b>Commander</b> sees a C2 leadership dashboard. Inject a <code>c2_jamming</code>
              event to see the situational feed become stale and conflicting.</li>
            <li><b>🛑 Kill switch</b> (Admin / Director) instantly halts every VM — use it to
              stop an exercise immediately.</li>
            <li>Everything is a harmless dummy — no real malware, identities, or credentials.</li>
          </ul>
        </div>

        <div className="guide-section">
          <h3>6 · Ransomware playbook <span className="role-note">MOD-05</span></h3>
          <p style={{ fontSize: 12.5, margin: "0 0 6px" }}>
            <b>Goal:</b> stop the spread, save the data, and restore operations as fast as
            possible — <b>without paying the ransom</b>. Fast isolation + clean backups win.
          </p>
          <ol>
            <li><b>Detect (TTD)</b> — <code>workstation-01</code> turns red; the SOC feed shows
              critical logs: <code>mass_file_rename ext=.locked</code>,
              <code>shadow_copy_delete</code>, <code>POST .../key</code>.</li>
            <li><b>Triage (TTT)</b> — confirm it's ransomware, find patient-zero and how far it
              has spread.</li>
            <li><b>Contain (TTC)</b> ⭐ — in <b>Containment</b>, <b>Quarantine</b> the infected
              host to isolate it from the network so encryption can't spread. If it's already
              widespread, hit the <b>🛑 Kill Switch</b>.</li>
            <li><b>Recover (TTR)</b> — <b>Restore</b> the host from a clean backup → status
              returns to UP.</li>
          </ol>
          <p style={{ fontSize: 12, color: "var(--muted)", margin: "4px 0 0" }}>
            Principles drilled: never pay the ransom · keep tested clean backups · isolate
            first, then eradicate and recover (don't restore before contained).
          </p>
        </div>
      </div>
    </div>
  );
}
