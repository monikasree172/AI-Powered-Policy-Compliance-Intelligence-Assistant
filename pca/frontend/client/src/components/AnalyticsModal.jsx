import { useState, useEffect } from "react";
import axios from "axios";
import "./AnalyticsModal.css";

const LEVELS = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "MINIMAL"];
const LEVEL_COLORS = { CRITICAL: "#c0392b", HIGH: "#92530a", MEDIUM: "#854d0e", LOW: "#0a7a3e", MINIMAL: "#0052cc" };
const STATUS_LABELS = { COMPLIANT: "Compliant", NON_COMPLIANT: "Non-Compliant", REQUIRES_REVIEW: "Review Required", INSUFFICIENT_INFO: "Insufficient Info" };

export default function AnalyticsModal({ onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    axios.get("/api/v1/analytics")
      .then(r => { setData(r.data); setLoading(false); })
      .catch(() => { setError("Could not load analytics."); setLoading(false); });
  }, []);

  const dist = data?.risk_distribution || {};
  const compDist = data?.compliance_status_distribution || {};
  const nistTop = data?.top_nist_functions || [];
  const recent = data?.recent_queries || [];
  const maxRisk = Math.max(...LEVELS.map(l => dist[l] || 0), 1);

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <div className="modal-header">
          <h2>Compliance Analytics</h2>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">
          {loading && <p className="modal-msg">Loading...</p>}
          {error && <p className="modal-msg error">{error}</p>}
          {data && <>
            <div className="analytics-grid">
              <div className="analytics-card"><div className="a-val">{data.total_queries || 0}</div><div className="a-lbl">Total Queries</div></div>
              <div className="analytics-card"><div className="a-val">{Math.round(data.avg_response_time_ms || 0)}</div><div className="a-lbl">Avg ms</div></div>
              <div className="analytics-card"><div className="a-val">{compDist["NON_COMPLIANT"] || 0}</div><div className="a-lbl">Non-Compliant</div></div>
            </div>
            <div className="modal-section-label">Risk Distribution</div>
            <div className="risk-bars">
              {LEVELS.map(l => (
                <div key={l} className="risk-bar-row">
                  <span className="rbl">{l}</span>
                  <div className="rbt"><div className="rbf" style={{ width: `${Math.round(((dist[l] || 0) / maxRisk) * 100)}%`, background: LEVEL_COLORS[l] }} /></div>
                  <span className="rbc">{dist[l] || 0}</span>
                </div>
              ))}
            </div>
            {nistTop.length > 0 && <>
              <div className="modal-section-label">Top NIST Functions</div>
              <div className="nist-tags">
                {nistTop.map(([fn, count]) => <span key={fn} className="nist-tag">{fn} <em>({count})</em></span>)}
              </div>
            </>}
            {recent.length > 0 && <>
              <div className="modal-section-label">Recent Queries</div>
              <div className="recent-list">
                {recent.slice(0, 5).map((q, i) => (
                  <div key={i} className="recent-item">
                    <span className="recent-q">{q.question_preview}</span>
                    <span className={`badge badge-${q.compliance_status}`}>{STATUS_LABELS[q.compliance_status] || q.compliance_status}</span>
                  </div>
                ))}
              </div>
            </>}
          </>}
        </div>
      </div>
    </div>
  );
}
