import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import Sidebar from "./components/Sidebar.jsx";
import ChatArea from "./components/ChatArea.jsx";
import InputBar from "./components/InputBar.jsx";
import AnalyticsModal from "./components/AnalyticsModal.jsx";
import "./App.css";

const AGENTS = [
  { key: "retrieval", label: "Retrieval" },
  { key: "interpretation", label: "Analysis" },
  { key: "compliance_checker", label: "Compliance" },
  { key: "risk_assessment", label: "Risk" },
  { key: "recommendation", label: "Response" },
];

export default function App() {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [apiStatus, setApiStatus] = useState({ online: false, docsIndexed: 0 });
  const [analyticsOpen, setAnalyticsOpen] = useState(false);
  const [filters, setFilters] = useState({ framework: "", nist_function: "" });
  const [sessionStats, setSessionStats] = useState({ queries: 0, tokens: 0, riskScores: [], times: [] });

  useEffect(() => {
    checkHealth();
    loadAnalytics();
  }, []);

  const checkHealth = async () => {
    try {
      const { data } = await axios.get("/api/v1/health", { timeout: 4000 });
      setApiStatus({ online: data.status === "healthy", docsIndexed: data.documents_indexed || 0 });
    } catch {
      setApiStatus({ online: false, docsIndexed: 0 });
    }
  };

  const loadAnalytics = async () => {
    try {
      const { data } = await axios.get("/api/v1/analytics", { timeout: 4000 });
      setSessionStats({
        queries: data.total_queries || 0,
        tokens: data.recent_queries?.reduce((a, q) => a + (q.tokens || 0), 0) || 0,
        riskScores: data.recent_queries?.map(q =>
          q.risk_level === "CRITICAL" ? 1.0 :
          q.risk_level === "HIGH" ? 0.75 :
          q.risk_level === "MEDIUM" ? 0.5 :
          q.risk_level === "LOW" ? 0.25 : 0.1
        ) || [],
        times: data.recent_queries?.map(q => q.response_time_ms || 0) || [],
      });
    } catch {
      console.log("Analytics not available");
    }
  };

  const submitQuery = useCallback(async (question) => {
    if (isLoading || !question.trim()) return;
    setIsLoading(true);
    setMessages(prev => [...prev, { type: "user", text: question }]);
    setMessages(prev => [...prev, { type: "loading", agents: AGENTS }]);
    try {
      const body = { question };
      if (filters.framework) body.filters = { ...body.filters, framework: filters.framework };
      if (filters.nist_function) body.filters = { ...body.filters, nist_function: filters.nist_function };
      const { data } = await axios.post("/api/v1/query", body, { timeout: 120000 });
      setMessages(prev => [...prev.filter(m => m.type !== "loading"), { type: "response", data }]);
      setSessionStats(prev => ({
        queries: prev.queries + 1,
        tokens: prev.tokens + (data.token_usage?.total || 0),
        riskScores: [...prev.riskScores, data.risk_score || 0],
        times: [...prev.times, data.response_time_ms || 0],
      }));
    } catch (err) {
      setMessages(prev => [...prev.filter(m => m.type !== "loading"), { type: "error", text: err.response?.data?.error || err.message || "Query failed" }]);
    }
    setIsLoading(false);
  }, [isLoading, filters]);

  return (
    <div className="app-layout">
      <header className="app-header">
        <div className="logo">
          <div className="logo-mark">
            <svg viewBox="0 0 20 20" fill="none" width="14" height="14">
              <path d="M10 2L3 6v8l7 4 7-4V6L10 2z" stroke="#22c55e" strokeWidth="1.5" fill="rgba(34,197,94,0.1)"/>
              <path d="M7 10l2 2 4-4" stroke="#22c55e" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <span className="logo-text">Compliance<em>AI</em></span>
        </div>
        <div className="header-divider" />
        <span className="header-subtitle">Policy Intelligence Platform</span>
        <div className="header-right">
          <div className="api-status">
            <span className={`status-dot ${apiStatus.online ? "online" : "offline"}`} />
            <span>{apiStatus.online ? `${apiStatus.docsIndexed} documents indexed` : "service offline"}</span>
          </div>
          <button className="btn-analytics" onClick={() => setAnalyticsOpen(true)}>Analytics</button>
        </div>
      </header>
      <div className="app-body">
        <Sidebar onSelectQuery={submitQuery} filters={filters} onFilterChange={setFilters} sessionStats={sessionStats} />
        <div className="main-col">
          <ChatArea messages={messages} isLoading={isLoading} onQuickQuery={submitQuery} />
          <InputBar onSubmit={submitQuery} isLoading={isLoading} />
        </div>
      </div>
      {analyticsOpen && <AnalyticsModal onClose={() => setAnalyticsOpen(false)} />}
    </div>
  );
}