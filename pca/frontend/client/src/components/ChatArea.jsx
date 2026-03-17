import { useEffect, useRef } from "react";
import ResponseCard from "./ResponseCard.jsx";
import LoadingCard from "./LoadingCard.jsx";
import "./ChatArea.css";

const QUICK = [
  "Can I share customer PII with a vendor?",
  "What to do after a phishing email?",
  "Remote work security requirements?",
  "Password policy for internal systems?",
];

export default function ChatArea({ messages, isLoading, onQuickQuery }) {
  const bottomRef = useRef(null);
  const areaRef = useRef(null);

  useEffect(() => {
    if (!bottomRef.current) return;
    const last = messages[messages.length - 1];
    if (last?.type === "response" || last?.type === "error") {
      const cards = areaRef.current?.querySelectorAll(".msg-wrapper");
      if (cards?.length) cards[cards.length - 1].scrollIntoView({ behavior: "smooth", block: "start" });
    } else {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="chat-area empty">
        <div className="empty-state">
          <div className="empty-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#22c55e" strokeWidth="1.5">
              <path d="M12 2l7 4v8l-7 4-7-4V6l7-4z" fill="rgba(34,197,94,0.1)"/>
              <path d="M9 12l2 2 4-4" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <h2>Ask a compliance question</h2>
          <p>The multi-agent system retrieves relevant policy sections and provides grounded compliance guidance with risk assessments.</p>
          <div className="empty-chips">
            {QUICK.map((q, i) => (
              <button key={i} className="empty-chip" onClick={() => onQuickQuery && onQuickQuery(q)}>{q}</button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-area" ref={areaRef}>
      {messages.map((msg, i) => (
        <div key={i} className="msg-wrapper">
          {msg.type === "user" && <div className="user-bubble">{msg.text}</div>}
          {msg.type === "loading" && <LoadingCard agents={msg.agents} />}
          {msg.type === "response" && <ResponseCard data={msg.data} />}
          {msg.type === "error" && <div className="error-card">{msg.text}</div>}
        </div>
      ))}
      <div ref={bottomRef} style={{ height: 8 }} />
    </div>
  );
}
