"""
Interpretation Microservice — Port 8002
Explains policy text in plain English using GPT-4o
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
    format="%(asctime)s [INTERPRETATION] %(levelname)s — %(message)s",
    handlers=[
        logging.FileHandler("logs/interpretation.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("interpretation")

app = FastAPI(title="Interpretation Service", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

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


class InterpretationRequest(BaseModel):
    question: str
    retrieved_chunks: list


class InterpretationResponse(BaseModel):
    interpretation: str
    key_clauses: list
    applicable_sections: list
    prompt_tokens: int
    completion_tokens: int
    response_time_ms: float


def _extract(text: str, section: str) -> str:
    m = re.search(rf"{section}:\s*(.+?)(?=\n[A-Z\s]+:|$)", text, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _extract_list(text: str, section: str) -> list:
    raw = _extract(text, section)
    if not raw:
        return []
    return [l.strip().lstrip("-•*123456789. ") for l in raw.split("\n") if l.strip().lstrip("-•*123456789. ")]


@app.get("/health")
def health():
    logger.info("Health check OK")
    return {"status": "healthy", "service": "interpretation", "port": 8002}


@app.post("/interpret", response_model=InterpretationResponse)
def interpret(request: InterpretationRequest):
    start = time.time()
    logger.info(f"Interpretation request — question: '{request.question[:80]}'")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY not set")
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

    if not request.retrieved_chunks:
        logger.warning("No chunks provided for interpretation")
        return InterpretationResponse(
            interpretation="No relevant policy documents found.",
            key_clauses=[], applicable_sections=[],
            prompt_tokens=0, completion_tokens=0, response_time_ms=0
        )

    try:
        client = OpenAI(api_key=api_key)
        context_parts = []
        for i, chunk in enumerate(request.retrieved_chunks, 1):
            meta = chunk.get("metadata", {})
            header = f"[Excerpt {i}] {meta.get('source', 'Unknown')}"
            if meta.get("subcategory"):
                header += f" | {meta['subcategory']}"
            if meta.get("nist_function"):
                header += f" | Function: {meta['nist_function']}"
            context_parts.append(f"{header}\n{chunk['text']}")

        user_message = f"""Employee Question:\n{request.question}\n\nRetrieved Policy Excerpts:\n{"---".join(context_parts)}\n\nFormat your response EXACTLY as:\nINTERPRETATION: [plain English explanation]\nKEY CLAUSES: [bullet list of relevant clauses]\nAPPLICABLE SECTIONS: [list of IDs like PR.DS-5, GV.OC-01]"""

        response = client.chat.completions.create(
            model="gpt-4o", max_tokens=1000,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_message}]
        )

        text = response.choices[0].message.content
        elapsed = (time.time() - start) * 1000
        logger.info(f"Interpretation complete in {elapsed:.1f}ms — tokens: {response.usage.total_tokens}")

        return InterpretationResponse(
            interpretation=_extract(text, "INTERPRETATION") or text,
            key_clauses=_extract_list(text, "KEY CLAUSES"),
            applicable_sections=_extract_list(text, "APPLICABLE SECTIONS"),
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            response_time_ms=round(elapsed, 1)
        )
    except Exception as e:
        logger.error(f"Interpretation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)
