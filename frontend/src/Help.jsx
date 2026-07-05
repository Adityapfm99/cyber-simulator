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
          <h3>3 · Commander &amp; safety</h3>
          <ul>
            <li><b>Commander</b> sees a C2 leadership dashboard. Inject a <code>c2_jamming</code>
              event to see the situational feed become stale and conflicting.</li>
            <li><b>🛑 Kill switch</b> (Admin / Director) instantly halts every VM — use it to
              stop an exercise immediately.</li>
            <li>Everything is a harmless dummy — no real malware, identities, or credentials.</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
