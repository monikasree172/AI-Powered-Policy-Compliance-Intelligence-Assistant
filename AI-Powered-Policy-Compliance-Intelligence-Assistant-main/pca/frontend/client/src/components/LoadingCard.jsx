import { useState, useEffect } from "react";
import "./LoadingCard.css";

export default function LoadingCard({ agents }) {
  const [activeIdx, setActiveIdx] = useState(0);
  const [doneIdxs, setDoneIdxs] = useState([]);

  useEffect(() => {
    const iv = setInterval(() => {
      setActiveIdx(prev => {
        if (prev < agents.length) {
          setDoneIdxs(d => [...d, prev - 1].filter(x => x >= 0));
          return prev + 1;
        }
        clearInterval(iv);
        return prev;
      });
    }, 700);
    return () => clearInterval(iv);
  }, [agents.length]);

  return (
    <div className="loading-card">
      <div className="pipeline-header">
        <div className="pipeline-spinner" />
        <span className="pipeline-title">Processing query through agent pipeline</span>
      </div>
      <div className="pipeline-track">
        {agents.map((agent, i) => {
          const isDone = doneIdxs.includes(i);
          const isActive = activeIdx === i;
          return (
            <div key={agent.key} className={`pipeline-step ${isDone ? "done" : ""} ${isActive ? "active" : ""}`}>
              <div className="step-node">
                <div className="step-dot" />
                <span className="step-label">{agent.label}</span>
              </div>
              {i < agents.length - 1 && <div className={`step-line ${isDone ? "filled" : ""}`} />}
            </div>
          );
        })}
      </div>
    </div>
  );
}
