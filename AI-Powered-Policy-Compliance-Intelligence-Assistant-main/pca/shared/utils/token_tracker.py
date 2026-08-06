"""Thread-safe token usage tracker across all agent calls."""

from dataclasses import dataclass
from threading import Lock


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


class TokenTracker:
    def __init__(self):
        self._usage: dict = {}
        self._lock = Lock()

    def record(self, agent_name: str, input_tokens: int, output_tokens: int):
        with self._lock:
            if agent_name not in self._usage:
                self._usage[agent_name] = TokenUsage()
            self._usage[agent_name].input_tokens += input_tokens
            self._usage[agent_name].output_tokens += output_tokens

    def totals(self) -> dict:
        with self._lock:
            per_agent = {
                name: {"input": u.input_tokens, "output": u.output_tokens, "total": u.total}
                for name, u in self._usage.items()
            }
            grand_input = sum(u.input_tokens for u in self._usage.values())
            grand_output = sum(u.output_tokens for u in self._usage.values())
            return {
                "per_agent": per_agent,
                "total_input": grand_input,
                "total_output": grand_output,
                "total": grand_input + grand_output,
            }
