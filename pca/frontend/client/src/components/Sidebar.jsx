import "./Sidebar.css";

const SAMPLE_QUESTIONS = [
  "Can I continue working remotely while traveling to another country for 3 months?",
  "I accidentally saw data that does not belong to my project. Should I report it?",
  "Are there restrictions when sharing customer data from different regions?",
  "What are the password and MFA requirements for internal systems?",
  "Can I share customer PII with a third-party vendor for analytics?",
];

function fmtNum(n) { return n >= 1000 ? (n / 1000).toFixed(1) + "k" : String(n); }

export default function Sidebar({ onSelectQuery, filters, onFilterChange, sessionStats }) {
  const avgRisk = sessionStats.riskScores.length
    ? (sessionStats.riskScores.reduce((a, b) => a + b, 0) / sessionStats.riskScores.length).toFixed(2) : "—";
  const avgTime = sessionStats.times.length
    ? Math.round(sessionStats.times.reduce((a, b) => a + b, 0) / sessionStats.times.length) : "—";

  return (
    <aside className="sidebar">
      <div className="sidebar-inner">
        <div className="sidebar-group">
          <div className="sidebar-group-header">
            <svg className="sidebar-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
            <span className="sidebar-group-label">Sample Queries</span>
          </div>
          <div className="sample-list">
            {SAMPLE_QUESTIONS.map((q, i) => (
              <button key={i} className="sample-btn" onClick={() => onSelectQuery(q)}>{q}</button>
            ))}
          </div>
        </div>

        <div className="sidebar-group">
          <div className="sidebar-group-header">
            <svg className="sidebar-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>
            <span className="sidebar-group-label">Filters</span>
          </div>
          <div className="filter-group">
            <div className="filter-row">
              <label>Framework</label>
              <select value={filters.framework} onChange={e => onFilterChange(f => ({ ...f, framework: e.target.value }))}>
                <option value="">All frameworks</option>
                <option value="NIST">NIST CSF</option>
                <option value="GDPR">GDPR</option>
              </select>
            </div>
            <div className="filter-row">
              <label>NIST Function</label>
              <select value={filters.nist_function} onChange={e => onFilterChange(f => ({ ...f, nist_function: e.target.value }))}>
                <option value="">All functions</option>
                <option value="GOVERN">GOVERN</option>
                <option value="IDENTIFY">IDENTIFY</option>
                <option value="PROTECT">PROTECT</option>
                <option value="DETECT">DETECT</option>
                <option value="RESPOND">RESPOND</option>
                <option value="RECOVER">RECOVER</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      <div className="stats-grid">
        <div className="stat-card"><div className="stat-val">{sessionStats.queries}</div><div className="stat-lbl">Queries</div></div>
        <div className="stat-card"><div className="stat-val">{fmtNum(sessionStats.tokens)}</div><div className="stat-lbl">Tokens</div></div>
        <div className="stat-card"><div className="stat-val">{avgRisk}</div><div className="stat-lbl">Avg Risk</div></div>
        <div className="stat-card"><div className="stat-val">{avgTime}</div><div className="stat-lbl">Avg ms</div></div>
      </div>
    </aside>
  );
}
