"""Compliance Checker Agent — determines COMPLIANT / NON_COMPLIANT / REQUIRES_REVIEW."""

import re
from typing import Optional
from openai import OpenAI
from shared.utils.token_tracker import TokenTracker

SYSTEM_PROMPT = """You are a Compliance Verification Officer expert in NIST CSF and enterprise policies.

Make a clear compliance determination:
- COMPLIANT: Action is clearly permitted
- NON_COMPLIANT: Action clearly violates policy
- REQUIRES_REVIEW: Gray area, needs human approval
- INSUFFICIENT_INFO: Not enough context to decide

Also detect conflicts between frameworks. Base all decisions only on provided policy text."""

VALID_STATUSES = ["COMPLIANT", "NON_COMPLIANT", "REQUIRES_REVIEW", "INSUFFICIENT_INFO"]


class ComplianceCheckerAgent:
    def __init__(self, client: OpenAI):
        self.client = client
        self.name = "compliance_checker"
        self.model = "gpt-4o"

    def run(self, question: str, interpretation: str, key_clauses: list,
            retrieved_chunks: list, tracker: Optional[TokenTracker] = None) -> dict:
        clauses_text = "\n".join(f"- {c}" for c in key_clauses) if key_clauses else "None"
        frameworks = list({c.get("metadata", {}).get("framework", "") for c in retrieved_chunks if c.get("metadata", {}).get("framework")})

        user_message = f"""Employee Question: {question}

Policy Interpretation: {interpretation}

Key Clauses:
{clauses_text}

Frameworks: {', '.join(frameworks) or 'Unknown'}

Format EXACTLY as:
STATUS: [COMPLIANT/NON_COMPLIANT/REQUIRES_REVIEW/INSUFFICIENT_INFO]
REASONING: [explanation citing policy sections]
VIOLATED_POLICIES: [comma-separated list or None]
CONFLICTS_DETECTED: [YES or NO]
CONFLICT_DETAILS: [description or None]"""

        response = self.client.chat.completions.create(
            model=self.model, max_tokens=800,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_message}],
        )

        if tracker:
            tracker.record(self.name, response.usage.prompt_tokens, response.usage.completion_tokens)

        text = response.choices[0].message.content
        status = _extract(text, "STATUS")
        if status not in VALID_STATUSES:
            status = "REQUIRES_REVIEW"

        violated_raw = _extract(text, "VIOLATED_POLICIES")
        violated = [v.strip() for v in violated_raw.split(",") if v.strip() and v.strip().lower() != "none"] if violated_raw else []
        conflicts_raw = _extract(text, "CONFLICTS_DETECTED")
        conflicts = conflicts_raw.upper().startswith("YES") if conflicts_raw else False
        conflict_details = _extract(text, "CONFLICT_DETAILS")

        return {
            "status": status,
            "reasoning": _extract(text, "REASONING") or text,
            "violated_policies": violated,
            "conflicts_detected": conflicts,
            "conflict_details": conflict_details if conflicts else "",
        }


def _extract(text: str, field: str) -> str:
    m = re.search(rf"{field}:\s*(.+?)(?=\n[A-Z_]+:|$)", text, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""
