"""Analytics tracker — persists to JSON file so data survives restarts."""
import json
import os
from collections import Counter
from datetime import datetime
from threading import Lock

ANALYTICS_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "logs", "analytics.json")

class AnalyticsTracker:
    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._query_log: list = []
        self._risk_counts: Counter = Counter()
        self._topic_counts: Counter = Counter()
        self._compliance_status_counts: Counter = Counter()
        self._initialized = True
        self._load()

    def _load(self):
        """Load analytics from JSON file if it exists."""
        try:
            if os.path.exists(ANALYTICS_FILE):
                with open(ANALYTICS_FILE, "r") as f:
                    data = json.load(f)
                self._query_log = data.get("query_log", [])
                self._risk_counts = Counter(data.get("risk_counts", {}))
                self._topic_counts = Counter(data.get("topic_counts", {}))
                self._compliance_status_counts = Counter(data.get("compliance_status_counts", {}))
                print(f"[Analytics] Loaded {len(self._query_log)} queries from disk")
        except Exception as e:
            print(f"[Analytics] Could not load analytics file: {e}")

    def _save(self):
        """Persist analytics to JSON file."""
        try:
            os.makedirs(os.path.dirname(ANALYTICS_FILE), exist_ok=True)
            with open(ANALYTICS_FILE, "w") as f:
                json.dump({
                    "query_log": self._query_log,
                    "risk_counts": dict(self._risk_counts),
                    "topic_counts": dict(self._topic_counts),
                    "compliance_status_counts": dict(self._compliance_status_counts),
                }, f, indent=2)
        except Exception as e:
            print(f"[Analytics] Could not save analytics file: {e}")

    def record_query(self, question: str, risk_level: str, compliance_status: str,
                     nist_functions_hit: list, response_time_ms: float, token_count: int):
        self._risk_counts[risk_level] += 1
        self._compliance_status_counts[compliance_status] += 1
        for fn in nist_functions_hit:
            if fn:
                self._topic_counts[fn] += 1
        self._query_log.append({
            "timestamp": datetime.utcnow().isoformat(),
            "question_preview": question[:80],
            "risk_level": risk_level,
            "compliance_status": compliance_status,
            "response_time_ms": response_time_ms,
            "tokens": token_count,
        })
        if len(self._query_log) > 1000:
            self._query_log = self._query_log[-1000:]
        self._save()

    def get_dashboard_data(self) -> dict:
        total = len(self._query_log)
        avg_time = sum(q["response_time_ms"] for q in self._query_log) / total if total > 0 else 0
        return {
            "total_queries": total,
            "avg_response_time_ms": round(avg_time, 1),
            "risk_distribution": dict(self._risk_counts),
            "compliance_status_distribution": dict(self._compliance_status_counts),
            "top_nist_functions": self._topic_counts.most_common(10),
            "recent_queries": self._query_log[-10:][::-1],
        }

analytics = AnalyticsTracker()