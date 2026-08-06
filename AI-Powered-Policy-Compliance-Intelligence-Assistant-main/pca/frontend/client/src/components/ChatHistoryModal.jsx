import "./AnalyticsModal.css";

export default function ChatHistoryModal({ chatHistory, onClose, onLoadChat, onNewChat }) {
  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <div className="modal-header">
          <h2>Chat History</h2>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">
          <button
            onClick={() => { onNewChat(); onClose(); }}
            style={{
              width: "100%", padding: "9px", marginBottom: "16px",
              background: "var(--accent-light)", border: "1px solid var(--accent-border)",
              borderRadius: "var(--radius-sm)", color: "var(--accent)",
              fontSize: "0.78rem", fontWeight: 600, cursor: "pointer",
              letterSpacing: "0.02em"
            }}
          >
            + New Chat
          </button>

          {chatHistory.length === 0 ? (
            <p className="modal-msg">No previous chats yet. Start a conversation!</p>
          ) : (
            <div className="recent-list">
              {chatHistory.map(chat => (
                <div
                  key={chat.id}
                  className="recent-item"
                  style={{ cursor: "pointer" }}
                  onClick={() => { onLoadChat(chat.id); onClose(); }}
                >
                  <div style={{ display: "flex", flexDirection: "column", gap: "3px", flex: 1 }}>
                    <span className="recent-q">{chat.title}</span>
                    <span style={{ fontSize: "0.65rem", color: "var(--muted2)" }}>
                      {chat.timestamp} · {chat.messages.filter(m => m.type === "user").length} queries
                    </span>
                  </div>
                  <span className="nist-tag" style={{ flexShrink: 0 }}>View</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
