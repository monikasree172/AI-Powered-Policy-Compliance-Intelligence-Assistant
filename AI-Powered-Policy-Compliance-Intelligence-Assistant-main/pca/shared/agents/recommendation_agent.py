"""Recommendation Agent — actionable next steps, escalation paths, compliant alternatives."""

import re
from typing import Optional
from openai import OpenAI
from shared.utils.token_tracker import TokenTracker

SYSTEM_PROMPT = """You are a Compliance Advisory Officer helping employees navigate policy requirements.

Your recommendations must be:
1. Specific and actionable
2. Grounded in policy
3. Proportional to the risk level
4. Empathetic to the employee's needs

Always give a clear next step. Never leave someone without direction."""


class RecommendationAgent:
    def __init__(self, client: OpenAI):
        self.client = client
        self.name = "recommendation"
        self.model = "gpt-4o"

    def run(self, question: str, compliance_status: str, risk_level: str, risk_factors: list,
            urgency: str, violated_policies: list, applicable_sections: list,
            tracker: Optional[TokenTracker] = None) -> dict:

        user_message = f"""Employee Question: {question}
Compliance Status: {compliance_status}
Risk Level: {risk_level} | Urgency: {urgency}
Risk Factors: {', '.join(risk_factors) if risk_factors else 'None'}
Violated Policies: {', '.join(violated_policies) if violated_policies else 'None'}
Applicable Sections: {', '.join(applicable_sections) if applicable_sections else 'General policy'}

Format EXACTLY as:
SUMMARY: [2-3 sentence plain English answer]
NEXT_STEPS: [numbered list of actions]
ESCALATION_REQUIRED: [YES or NO]
ESCALATION_PATH: [who to contact, or Not required]
COMPLIANT_ALTERNATIVE: [specific alternative, or Current approach is compliant]
CITATIONS: [policy section IDs]"""

        response = self.client.chat.completions.create(
            model=self.model, max_tokens=900,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_message}],
        )

        if tracker:
            tracker.record(self.name, response.usage.prompt_tokens, response.usage.completion_tokens)

        text = response.choices[0].message.content
        escalation_raw = _extract(text, "ESCALATION_REQUIRED")
        escalation_required = escalation_raw.upper().startswith("YES") if escalation_raw else risk_level in ["CRITICAL", "HIGH"]
        escalation_path = _extract(text, "ESCALATION_PATH")
        if escalation_path.lower() in ("not required", ""):
            escalation_path = None
        compliant_alt = _extract(text, "COMPLIANT_ALTERNATIVE")
        if compliant_alt.lower() == "current approach is compliant":
            compliant_alt = None
        citations = _extract_list(text, "CITATIONS")
        all_citations = list(dict.fromkeys(citations + applicable_sections))

        return {
            "summary": _extract(text, "SUMMARY") or "Please review applicable policies before proceeding.",
            "next_steps": _extract_list(text, "NEXT_STEPS"),
            "escalation_required": escalation_required,
            "escalation_path": escalation_path,
            "compliant_alternative": compliant_alt,
            "citations": all_citations,
        }


def _extract(text: str, field: str) -> str:
    m = re.search(rf"{field}:\s*(.+?)(?=\n[A-Z_]+:|$)", text, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""

def _extract_list(text: str, field: str) -> list:
    raw = _extract(text, field)
    if not raw:
        return []
    return [l.strip().lstrip("-•*123456789. ") for l in raw.split("\n") if l.strip().lstrip("-•*123456789. ")]
