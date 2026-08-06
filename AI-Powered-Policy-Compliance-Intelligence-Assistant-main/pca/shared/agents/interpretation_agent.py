"""Policy Interpretation Agent — explains policy in plain English using OpenAI."""

import re
from typing import Optional
from openai import OpenAI
from shared.utils.token_tracker import TokenTracker

SYSTEM_PROMPT = """You are a Policy Interpretation Specialist with deep expertise in:
- NIST Cybersecurity Framework (CSF 2.0)
- Data governance and privacy regulations (GDPR, CCPA)
- Enterprise HR and cybersecurity policies

Your role:
1. Read retrieved policy excerpts carefully
2. Identify clauses most relevant to the employee's question
3. Explain complex regulatory language in plain English
4. Highlight key obligations, permissions, and restrictions

Always cite specific policy sections. Never invent requirements not in the documents."""


class PolicyInterpretationAgent:
    def __init__(self, client: OpenAI):
        self.client = client
        self.name = "interpretation"
        self.model = "gpt-4o"

    def run(self, question: str, retrieved_chunks: list, tracker: Optional[TokenTracker] = None) -> dict:
        if not retrieved_chunks:
            return {"interpretation": "No relevant policy documents found.", "key_clauses": [], "applicable_sections": []}

        context_parts = []
        for i, chunk in enumerate(retrieved_chunks, 1):
            meta = chunk.get("metadata", {})
            header = f"[Excerpt {i}] {meta.get('source', 'Unknown')}"
            if meta.get("subcategory"):
                header += f" | {meta['subcategory']}"
            if meta.get("nist_function"):
                header += f" | Function: {meta['nist_function']}"
            context_parts.append(f"{header}\n{chunk['text']}")

        user_message = f"""Employee Question:
{question}

Retrieved Policy Excerpts:
{"---".join(context_parts)}

Format your response EXACTLY as:
INTERPRETATION: [plain English explanation]
KEY CLAUSES: [bullet list of relevant clauses]
APPLICABLE SECTIONS: [list of IDs like PR.DS-5, GV.OC-01]"""

        response = self.client.chat.completions.create(
            model=self.model, max_tokens=1000,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_message}],
        )

        if tracker:
            tracker.record(self.name, response.usage.prompt_tokens, response.usage.completion_tokens)

        text = response.choices[0].message.content
        return {
            "interpretation": _extract(text, "INTERPRETATION") or text,
            "key_clauses": _extract_list(text, "KEY CLAUSES"),
            "applicable_sections": _extract_list(text, "APPLICABLE SECTIONS"),
            "raw_response": text,
        }


def _extract(text: str, section: str) -> str:
    m = re.search(rf"{section}:\s*(.+?)(?=\n[A-Z\s]+:|$)", text, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""

def _extract_list(text: str, section: str) -> list:
    raw = _extract(text, section)
    if not raw:
        return []
    return [l.strip().lstrip("-•*123456789. ") for l in raw.split("\n") if l.strip().lstrip("-•*123456789. ")]
