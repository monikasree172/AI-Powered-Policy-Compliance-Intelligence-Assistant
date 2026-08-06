import { useState, useRef } from "react";
import "./InputBar.css";
export default function InputBar({ onSubmit, isLoading, onNewChat }) {
  const [value, setValue] = useState("");
  const textareaRef = useRef(null);
  const handleInput = (e) => {
    setValue(e.target.value);
    const el = textareaRef.current;
    if (el) { el.style.height = "auto"; el.style.height = Math.min(el.scrollHeight, 120) + "px"; }
  };
  const handleKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); }
  };
  const submit = () => {
    const q = value.trim();
    if (!q || isLoading) return;
    onSubmit(q);
    setValue("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  };
  return (
    <div className="input-bar">
      <div className="input-wrapper">
        <textarea
          ref={textareaRef}
          className="query-input"
          value={value}
          onChange={handleInput}
          onKeyDown={handleKey}
          placeholder="Ask a compliance question..."
          rows={1}
          disabled={isLoading}
        />
        <button className="send-btn" onClick={submit} disabled={isLoading || !value.trim()}>
          {isLoading ? <span className="spinner" /> : (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="14" height="14">
              <path d="M22 2L11 13M22 2L15 22l-4-9-9-4 20-7z"/>
            </svg>
          )}
          {isLoading ? "Analyzing..." : "Submit"}
        </button>
        <button className="new-chat-inline-btn" onClick={onNewChat} disabled={isLoading} title="New Chat">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="14" height="14">
            <line x1="12" y1="5" x2="12" y2="19"/>
            <line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          New Chat
        </button>
      </div>
      <p className="input-hint">Enter to submit · Shift+Enter for new line</p>
    </div>
  );
}
