"""Risk Assessment Agent — scores violation severity from 0.0 to 1.0."""

import re
from typing import Optional
from openai import OpenAI
from shared.utils.token_tracker import TokenTracker

SYSTEM_PROMPT = """You are a Chief Risk Officer specializing in cybersecurity and data governance.

Score compliance risk based on: data sensitivity, regulatory exposure, business impact, and likelihood of harm.

Risk Levels:
- CRITICAL (0.85-1.0): Severe — likely penalties or breach
- HIGH (0.65-0.84): Significant material consequences
- MEDIUM (0.40-0.64): Moderate, needs attention
- LOW (0.20-0.39): Minor, limited impact
- MINIMAL (0.0-0.19): Negligible risk

Always provide a numeric score 0.0–1.0."""


class RiskAssessmentAgent:
    def __init__(self, client: OpenAI):
        self.client = client
        self.name = "risk_assessment"
        self.model = "gpt-4o"

    def run(self, question: str, compliance_status: str, reasoning: str,
            violated_policies: list, tracker: Optional[TokenTracker] = None) -> dict:
        violated_text = "\n".join(f"- {v}" for v in violated_policies) if violated_policies else "None"

        user_message = f"""Question: {question}
Compliance Status: {compliance_status}
Reasoning: {reasoning}
Violated Policies:
{violated_text}

Format EXACTLY as:
RISK_LEVEL: [CRITICAL/HIGH/MEDIUM/LOW/MINIMAL]
RISK_SCORE: [0.0 to 1.0]
RISK_FACTORS: [bullet list]
POTENTIAL_CONSEQUENCES: [description]
URGENCY: [IMMEDIATE/WITHIN_24H/WITHIN_WEEK/ROUTINE]"""

        response = self.client.chat.completions.create(
            model=self.model, max_tokens=600,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_message}],
        )

        if tracker:
            tracker.record(self.name, response.usage.prompt_tokens, response.usage.completion_tokens)

        text = response.choices[0].message.content
        risk_level = _extract(text, "RISK_LEVEL")
        if risk_level not in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "MINIMAL"]:
            risk_level = _default_level(compliance_status)

        try:
            risk_score = max(0.0, min(1.0, float(_extract(text, "RISK_SCORE"))))
        except (ValueError, TypeError):
            risk_score = _default_score(risk_level)

        factors_raw = _extract(text, "RISK_FACTORS")
        factors = [l.strip().lstrip("-•*123456789. ") for l in factors_raw.split("\n") if l.strip().lstrip("-•*123456789. ")] if factors_raw else []
        urgency = _extract(text, "URGENCY")
        if urgency not in ["IMMEDIATE", "WITHIN_24H", "WITHIN_WEEK", "ROUTINE"]:
            urgency = _default_urgency(risk_level)

        return {
            "risk_level": risk_level, "risk_score": risk_score, "risk_factors": factors,
            "potential_consequences": _extract(text, "POTENTIAL_CONSEQUENCES") or "Not assessed",
            "urgency": urgency,
        }


def _extract(text: str, field: str) -> str:
    m = re.search(rf"{field}:\s*(.+?)(?=\n[A-Z_]+:|$)", text, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""

def _default_level(s): return {"NON_COMPLIANT": "HIGH", "REQUIRES_REVIEW": "MEDIUM", "COMPLIANT": "LOW", "INSUFFICIENT_INFO": "MEDIUM"}.get(s, "MEDIUM")
def _default_score(l): return {"CRITICAL": 0.92, "HIGH": 0.75, "MEDIUM": 0.50, "LOW": 0.25, "MINIMAL": 0.10}.get(l, 0.5)
def _default_urgency(l): return {"CRITICAL": "IMMEDIATE", "HIGH": "WITHIN_24H", "MEDIUM": "WITHIN_WEEK", "LOW": "ROUTINE", "MINIMAL": "ROUTINE"}.get(l, "WITHIN_WEEK")
