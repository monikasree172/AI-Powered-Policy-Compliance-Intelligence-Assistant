"""
Compliance Checker Microservice — Port 8003
Determines COMPLIANT / NON_COMPLIANT / REQUIRES_REVIEW using GPT-4o
"""

import os
import re
import logging
import time
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [COMPLIANCE] %(levelname)s — %(message)s",
    handlers=[
        logging.FileHandler("logs/compliance.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("compliance")

app = FastAPI(title="Compliance Checker Service", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

SYSTEM_PROMPT = """You are a Compliance Verification Officer expert in NIST CSF and enterprise policies.

Make a clear compliance determination:
- COMPLIANT: Action is clearly permitted
- NON_COMPLIANT: Action clearly violates policy
- REQUIRES_REVIEW: Gray area, needs human approval
- INSUFFICIENT_INFO: Not enough context to decide

Also detect conflicts between frameworks. Base all decisions only on provided policy text."""

VALID_STATUSES = ["COMPLIANT", "NON_COMPLIANT", "REQUIRES_REVIEW", "INSUFFICIENT_INFO"]


class ComplianceRequest(BaseModel):
    question: str
    interpretation: str
    key_clauses: list
    retrieved_chunks: list


class ComplianceResponse(BaseModel):
    status: str
    reasoning: str
    violated_policies: list
    conflicts_detected: bool
    conflict_details: str
    prompt_tokens: int
    completion_tokens: int
    response_time_ms: float


def _extract(text: str, field: str) -> str:
    m = re.search(rf"{field}:\s*(.+?)(?=\n[A-Z_]+:|$)", text, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""


@app.get("/health")
def health():
    logger.info("Health check OK")
    return {"status": "healthy", "service": "compliance", "port": 8003}


@app.post("/check", response_model=ComplianceResponse)
def check_compliance(request: ComplianceRequest):
    start = time.time()
    logger.info(f"Compliance check — question: '{request.question[:80]}'")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY not set")
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

    try:
        client = OpenAI(api_key=api_key)
        clauses_text = "\n".join(f"- {c}" for c in request.key_clauses) if request.key_clauses else "None"
        frameworks = list({c.get("metadata", {}).get("framework", "") for c in request.retrieved_chunks if c.get("metadata", {}).get("framework")})

        user_message = f"""Employee Question: {request.question}

Policy Interpretation: {request.interpretation}

Key Clauses:
{clauses_text}

Frameworks: {', '.join(frameworks) or 'Unknown'}

Format EXACTLY as:
STATUS: [COMPLIANT/NON_COMPLIANT/REQUIRES_REVIEW/INSUFFICIENT_INFO]
REASONING: [explanation citing policy sections]
VIOLATED_POLICIES: [comma-separated list or None]
CONFLICTS_DETECTED: [YES or NO]
CONFLICT_DETAILS: [description or None]"""

        response = client.chat.completions.create(
            model="gpt-4o", max_tokens=800,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_message}]
        )

        text = response.choices[0].message.content
        status = _extract(text, "STATUS")
        if status not in VALID_STATUSES:
            status = "REQUIRES_REVIEW"

        violated_raw = _extract(text, "VIOLATED_POLICIES")
        violated = [v.strip() for v in violated_raw.split(",") if v.strip() and v.strip().lower() != "none"] if violated_raw else []
        conflicts_raw = _extract(text, "CONFLICTS_DETECTED")
        conflicts = conflicts_raw.upper().startswith("YES") if conflicts_raw else False
        conflict_details = _extract(text, "CONFLICT_DETAILS")

        elapsed = (time.time() - start) * 1000
        logger.info(f"Compliance result: {status} in {elapsed:.1f}ms — conflicts: {conflicts}")

        return ComplianceResponse(
            status=status,
            reasoning=_extract(text, "REASONING") or text,
            violated_policies=violated,
            conflicts_detected=conflicts,
            conflict_details=conflict_details if conflicts else "",
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            response_time_ms=round(elapsed, 1)
        )
    except Exception as e:
        logger.error(f"Compliance check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8003, reload=True)
