"""
Risk Assessment Microservice — Port 8004
Scores violation severity 0.0 to 1.0 using GPT-4o
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
    format="%(asctime)s [RISK] %(levelname)s — %(message)s",
    handlers=[
        logging.FileHandler("logs/risk.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("risk")

app = FastAPI(title="Risk Assessment Service", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

SYSTEM_PROMPT = """You are a Chief Risk Officer specializing in cybersecurity and data governance.

Score compliance risk based on: data sensitivity, regulatory exposure, business impact, and likelihood of harm.

Risk Levels:
- CRITICAL (0.85-1.0): Severe — likely penalties or breach
- HIGH (0.65-0.84): Significant material consequences
- MEDIUM (0.40-0.64): Moderate, needs attention
- LOW (0.20-0.39): Minor, limited impact
- MINIMAL (0.0-0.19): Negligible risk

Always provide a numeric score 0.0—1.0."""

VALID_LEVELS = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "MINIMAL"]
VALID_URGENCIES = ["IMMEDIATE", "WITHIN_24H", "WITHIN_WEEK", "ROUTINE"]


class RiskRequest(BaseModel):
    question: str
    compliance_status: str
    reasoning: str
    violated_policies: list


class RiskResponse(BaseModel):
    risk_level: str
    risk_score: float
    risk_factors: list
    potential_consequences: str
    urgency: str
    prompt_tokens: int
    completion_tokens: int
    response_time_ms: float


def _extract(text: str, field: str) -> str:
    m = re.search(rf"{field}:\s*(.+?)(?=\n[A-Z_]+:|$)", text, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""

def _default_level(s): return {"NON_COMPLIANT": "HIGH", "REQUIRES_REVIEW": "MEDIUM", "COMPLIANT": "LOW", "INSUFFICIENT_INFO": "MEDIUM"}.get(s, "MEDIUM")
def _default_score(l): return {"CRITICAL": 0.92, "HIGH": 0.75, "MEDIUM": 0.50, "LOW": 0.25, "MINIMAL": 0.10}.get(l, 0.5)
def _default_urgency(l): return {"CRITICAL": "IMMEDIATE", "HIGH": "WITHIN_24H", "MEDIUM": "WITHIN_WEEK", "LOW": "ROUTINE", "MINIMAL": "ROUTINE"}.get(l, "WITHIN_WEEK")


@app.get("/health")
def health():
    logger.info("Health check OK")
    return {"status": "healthy", "service": "risk", "port": 8004}


@app.post("/assess", response_model=RiskResponse)
def assess_risk(request: RiskRequest):
    start = time.time()
    logger.info(f"Risk assessment — status: {request.compliance_status} question: '{request.question[:60]}'")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY not set")
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

    try:
        client = OpenAI(api_key=api_key)
        violated_text = "\n".join(f"- {v}" for v in request.violated_policies) if request.violated_policies else "None"

        user_message = f"""Question: {request.question}
Compliance Status: {request.compliance_status}
Reasoning: {request.reasoning}
Violated Policies:
{violated_text}

Format EXACTLY as:
RISK_LEVEL: [CRITICAL/HIGH/MEDIUM/LOW/MINIMAL]
RISK_SCORE: [0.0 to 1.0]
RISK_FACTORS: [bullet list]
POTENTIAL_CONSEQUENCES: [description]
URGENCY: [IMMEDIATE/WITHIN_24H/WITHIN_WEEK/ROUTINE]"""

        response = client.chat.completions.create(
            model="gpt-4o", max_tokens=600,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_message}]
        )

        text = response.choices[0].message.content
        risk_level = _extract(text, "RISK_LEVEL")
        if risk_level not in VALID_LEVELS:
            risk_level = _default_level(request.compliance_status)

        try:
            risk_score = max(0.0, min(1.0, float(_extract(text, "RISK_SCORE"))))
        except (ValueError, TypeError):
            risk_score = _default_score(risk_level)

        factors_raw = _extract(text, "RISK_FACTORS")
        factors = [l.strip().lstrip("-•*123456789. ") for l in factors_raw.split("\n") if l.strip().lstrip("-•*123456789. ")] if factors_raw else []

        urgency = _extract(text, "URGENCY")
        if urgency not in VALID_URGENCIES:
            urgency = _default_urgency(risk_level)

        elapsed = (time.time() - start) * 1000
        logger.info(f"Risk result: {risk_level} ({risk_score:.2f}) urgency={urgency} in {elapsed:.1f}ms")

        return RiskResponse(
            risk_level=risk_level, risk_score=risk_score,
            risk_factors=factors,
            potential_consequences=_extract(text, "POTENTIAL_CONSEQUENCES") or "Not assessed",
            urgency=urgency,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            response_time_ms=round(elapsed, 1)
        )
    except Exception as e:
        logger.error(f"Risk assessment failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8004, reload=True)
