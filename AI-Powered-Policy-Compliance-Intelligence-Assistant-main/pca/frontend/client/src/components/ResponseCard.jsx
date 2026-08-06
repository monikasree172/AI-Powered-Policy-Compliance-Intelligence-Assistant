import { useState } from "react";
import "./ResponseCard.css";

const STATUS_LABELS = {
  COMPLIANT: "Compliant", NON_COMPLIANT: "Non-Compliant",
  REQUIRES_REVIEW: "Review Required", INSUFFICIENT_INFO: "Insufficient Info",
};

const RISK_COLORS = {
  CRITICAL: "#ef4444", HIGH: "#f59e0b", MEDIUM: "#fbbf24", LOW: "#22c55e", MINIMAL: "#38bdf8",
};

export default function ResponseCard({ data }) {
  const [expandedSections, setExpandedSections] = useState({ steps: true, citations: false, explanation: false });

  const toggleSection = (key) => setExpandedSections(prev => ({ ...prev, [key]: !prev[key] }));

  const scoreWidth = Math.round((data.risk_score || 0) * 100);
  const barColor = RISK_COLORS[data.risk_level] || "#9ca3af";

  return (
    <div className="response-card">
      <div className="response-status-bar">
        <div className={`status-indicator ${data.compliance_status}`} />
        <div className="response-header">
          <span className={`badge badge-${data.compliance_status}`}>{STATUS_LABELS[data.compliance_status] || data.compliance_status}</span>
          <span className={`risk-pill risk-${data.risk_level}`}>{data.risk_level}</span>
          {(data.frameworks?.[0]) && <span className="framework-tag">{data.frameworks[0]}</span>}
          {data.urgency && <span className="urgency-tag">{data.urgency}</span>}
          <div className="risk-score-area">
            <span className="score-label">Risk {(data.risk_score || 0).toFixed(2)}</span>
            <div className="bar-track"><div className="bar-fill" style={{ width: `${scoreWidth}%`, background: barColor }} /></div>
          </div>
        </div>
      </div>

      <div className="response-body">
        <p className="answer-text">{data.answer}</p>

        {data.conflicts_detected && (
          <div className="conflict-box"><strong>Policy Conflict Detected — </strong>{data.conflict_details}</div>
        )}

        {data.next_steps?.length > 0 && (
          <div className="section">
            <div className="section-label" style={{ cursor: "pointer", display: "flex", justifyContent: "space-between" }}
              onClick={() => toggleSection("steps")}>
              <span>Recommended Actions ({data.next_steps.length})</span>
              <span style={{ opacity: 0.5 }}>{expandedSections.steps ? "▲" : "▼"}</span>
            </div>
            {expandedSections.steps && (
              <div className="steps-list">
                {data.next_steps.map((step, i) => (
                  <div key={i} className="step">
                    <div className="step-num">{i + 1}</div>
                    <span>{step}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {data.escalation_required && data.escalation_path && (
          <div className="escalation-box">
            <div><strong>Escalation Required</strong><p>{data.escalation_path}</p></div>
          </div>
        )}

        {data.compliant_alternative && (
          <div className="alt-box">
            <div className="section-label">Compliant Alternative</div>
            <p>{data.compliant_alternative}</p>
          </div>
        )}

        {data.citations?.length > 0 && (
          <div className="section">
            <div className="section-label" style={{ cursor: "pointer", display: "flex", justifyContent: "space-between" }}
              onClick={() => toggleSection("citations")}>
              <span>Policy References ({data.citations.length})</span>
              <span style={{ opacity: 0.5 }}>{expandedSections.citations ? "▲" : "▼"}</span>
            </div>
            {expandedSections.citations && (
              <div className="citations-list">
                {data.citations.map((c, i) => (
                  <div key={i} className="citation-item">
                    <div className="citation-source">{c.source} · {c.section}</div>
                    <div className="citation-text">{c.text_excerpt}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="response-footer">
        <span>{(data.agents_used || []).join(" → ")}</span>
        <span className="sep">|</span>
        <span>{data.token_usage?.total || 0} tokens</span>
        {data.response_time_ms && <><span className="sep">|</span><span>{Math.round(data.response_time_ms)}ms</span></>}
      </div>
    </div>
  );
}
