"""
Recommendation Microservice — Port 8005
Generates actionable next steps, escalation paths, compliant alternatives
"""

import os
import re
import logging
import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [RECOMMENDATION] %(levelname)s — %(message)s",
    handlers=[
        logging.FileHandler("logs/recommendation.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("recommendation")

app = FastAPI(title="Recommendation Service", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

SYSTEM_PROMPT = """You are a Compliance Advisory Officer helping employees navigate policy requirements.

Your recommendations must be:
1. Specific and actionable
2. Grounded in policy
3. Proportional to the risk level
4. Empathetic to the employee's needs

Always give a clear next step. Never leave someone without direction."""


class RecommendationRequest(BaseModel):
    question: str
    compliance_status: str
    risk_level: str
    risk_factors: list
    urgency: str
    violated_policies: list
    applicable_sections: list


class RecommendationResponse(BaseModel):
    summary: str
    next_steps: list
    escalation_required: bool
    escalation_path: str
    compliant_alternative: str
    citations: list
    prompt_tokens: int
    completion_tokens: int
    response_time_ms: float


def _extract(text: str, field: str) -> str:
    m = re.search(rf"{field}:\s*(.+?)(?=\n[A-Z_]+:|$)", text, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""

def _extract_list(text: str, field: str) -> list:
    raw = _extract(text, field)
    if not raw:
        return []
    return [l.strip().lstrip("-•*123456789. ") for l in raw.split("\n") if l.strip().lstrip("-•*123456789. ")]


@app.get("/health")
def health():
    logger.info("Health check OK")
    return {"status": "healthy", "service": "recommendation", "port": 8005}


@app.post("/recommend", response_model=RecommendationResponse)
def recommend(request: RecommendationRequest):
    start = time.time()
    logger.info(f"Recommendation — status: {request.compliance_status} risk: {request.risk_level}")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY not set")
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

    try:
        client = OpenAI(api_key=api_key)

        user_message = f"""Employee Question: {request.question}
Compliance Status: {request.compliance_status}
Risk Level: {request.risk_level} | Urgency: {request.urgency}
Risk Factors: {', '.join(request.risk_factors) if request.risk_factors else 'None'}
Violated Policies: {', '.join(request.violated_policies) if request.violated_policies else 'None'}
Applicable Sections: {', '.join(request.applicable_sections) if request.applicable_sections else 'General policy'}

Format EXACTLY as:
SUMMARY: [2-3 sentence plain English answer]
NEXT_STEPS: [numbered list of actions]
ESCALATION_REQUIRED: [YES or NO]
ESCALATION_PATH: [who to contact, or Not required]
COMPLIANT_ALTERNATIVE: [specific alternative, or Current approach is compliant]
CITATIONS: [policy section IDs]"""

        response = client.chat.completions.create(
            model="gpt-4o", max_tokens=900,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_message}]
        )

        text = response.choices[0].message.content
        escalation_raw = _extract(text, "ESCALATION_REQUIRED")
        escalation_required = escalation_raw.upper().startswith("YES") if escalation_raw else request.risk_level in ["CRITICAL", "HIGH"]
        escalation_path = _extract(text, "ESCALATION_PATH") or "Not required"
        compliant_alt = _extract(text, "COMPLIANT_ALTERNATIVE") or "Current approach is compliant"
        citations = _extract_list(text, "CITATIONS")
        all_citations = list(dict.fromkeys(citations + request.applicable_sections))

        elapsed = (time.time() - start) * 1000
        logger.info(f"Recommendation complete in {elapsed:.1f}ms — escalation: {escalation_required}")

        return RecommendationResponse(
            summary=_extract(text, "SUMMARY") or "Please review applicable policies before proceeding.",
            next_steps=_extract_list(text, "NEXT_STEPS"),
            escalation_required=escalation_required,
            escalation_path=escalation_path,
            compliant_alternative=compliant_alt,
            citations=all_citations,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            response_time_ms=round(elapsed, 1)
        )
    except Exception as e:
        logger.error(f"Recommendation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8005, reload=True)
