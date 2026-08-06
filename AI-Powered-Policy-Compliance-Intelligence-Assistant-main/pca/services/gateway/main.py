"""
API Gateway - Port 8000
Orchestrates all 5 microservices via HTTP calls
"""

import os
import sys
import logging
import time
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import httpx
from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from shared.utils.analytics import analytics
from shared.core.guardrails import validate_query, get_rejection_response

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [GATEWAY] %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/gateway.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("gateway")

app = FastAPI(
    title="ComplianceAI API Gateway",
    description="Microservices orchestrator for Policy Compliance Intelligence",
    version="2.0.0"
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

RETRIEVAL_URL      = os.getenv("RETRIEVAL_URL",      "http://localhost:8001")
INTERPRETATION_URL = os.getenv("INTERPRETATION_URL", "http://localhost:8002")
COMPLIANCE_URL     = os.getenv("COMPLIANCE_URL",     "http://localhost:8003")
RISK_URL           = os.getenv("RISK_URL",           "http://localhost:8004")
RECOMMENDATION_URL = os.getenv("RECOMMENDATION_URL", "http://localhost:8005")

TIMEOUT = 120.0


class QueryContext(BaseModel):
    department: Optional[str] = None
    region: Optional[str] = None
    role: Optional[str] = None


class QueryFilters(BaseModel):
    framework: Optional[str] = None
    nist_function: Optional[str] = None
    category: Optional[str] = None


class ComplianceQueryRequest(BaseModel):
    question: str = Field(..., min_length=5, max_length=1000)
    context: Optional[QueryContext] = None
    filters: Optional[QueryFilters] = None


def _build_citations(chunks: list) -> list:
    citations = []
    seen = set()
    for chunk in chunks[:5]:
        meta = chunk.get("metadata", {})
        source = meta.get("source", "Policy Document")
        subcategory = meta.get("subcategory", "")
        cid = f"{source}::{subcategory}"
        if cid in seen:
            continue
        seen.add(cid)
        citations.append({
            "source": source,
            "section": subcategory or meta.get("nist_function", "") or "General",
            "framework": meta.get("framework", ""),
            "nist_function": meta.get("nist_function", ""),
            "text_excerpt": chunk["text"][:200] + "..." if len(chunk["text"]) > 200 else chunk["text"],
            "relevance_score": round(chunk.get("score", 0), 4),
        })
    return citations


@app.get("/api/v1/health")
async def health():
    logger.info("Gateway health check")
    services = {}
    doc_count = 0

    async with httpx.AsyncClient(timeout=3.0) as client:
        for name, url in [
            ("retrieval", RETRIEVAL_URL),
            ("interpretation", INTERPRETATION_URL),
            ("compliance", COMPLIANCE_URL),
            ("risk", RISK_URL),
            ("recommendation", RECOMMENDATION_URL),
        ]:
            try:
                r = await client.get(f"{url}/health")
                data = r.json()
                services[name] = data.get("status", "unknown")
                if name == "retrieval":
                    doc_count = data.get("documents_indexed", 0)
            except Exception:
                services[name] = "offline"

    all_healthy = all(s == "healthy" for s in services.values())
    logger.info(f"Services status: {services} - docs: {doc_count}")

    return {
        "status": "healthy" if all_healthy else "degraded",
        "version": "2.0.0",
        "architecture": "microservices",
        "documents_indexed": doc_count,
        "agents": ["retrieval", "interpretation", "compliance_checker", "risk_assessment", "recommendation"],
        "services": services,
    }


@app.post("/api/v1/query")
async def compliance_query(request: ComplianceQueryRequest):
    start_time = time.time()
    question = request.question

    # Run guardrails first - reject invalid/off-topic queries immediately
    guard = validate_query(question)
    if not guard.is_valid:
        return get_rejection_response(guard.reason)

    filters = request.filters.model_dump(exclude_none=True) if request.filters else None
    agents_used = []
    token_usage = {"total_input": 0, "total_output": 0, "total": 0}
    use_fallback = False
    chunks = []

    logger.info(f"New query received: '{question[:80]}'")

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:

        # Step 1: Retrieval - always runs, no GPT-4o involved
        logger.info("Calling Retrieval Service (port 8001)...")
        try:
            ret_resp = await client.post(f"{RETRIEVAL_URL}/retrieve", json={
                "query": question, "top_k": 5, "filters": filters
            })
            ret_resp.raise_for_status()
            ret = ret_resp.json()
            agents_used.append("retrieval")
            chunks = ret["chunks"]
            logger.info(f"Retrieval: {ret['total_found']} chunks in {ret['response_time_ms']}ms")
        except Exception as e:
            logger.error(f"Retrieval service failed: {e}")
            raise HTTPException(status_code=503, detail=f"Retrieval service error: {str(e)}")

        if ret["total_found"] == 0:
            return {"success": False, "error": "No policy documents ingested.", "question": question}

        # Steps 2-5: GPT-4o pipeline with fallback
        try:
            # Step 2: Interpretation
            logger.info("Calling Interpretation Service (port 8002)...")
            interp_resp = await client.post(f"{INTERPRETATION_URL}/interpret", json={
                "question": question, "retrieved_chunks": chunks
            })
            interp_resp.raise_for_status()
            interp = interp_resp.json()
            agents_used.append("interpretation")
            token_usage["total_input"] += interp["prompt_tokens"]
            token_usage["total_output"] += interp["completion_tokens"]

            # Step 3: Compliance
            logger.info("Calling Compliance Service (port 8003)...")
            comp_resp = await client.post(f"{COMPLIANCE_URL}/check", json={
                "question": question,
                "interpretation": interp["interpretation"],
                "key_clauses": interp["key_clauses"],
                "retrieved_chunks": chunks
            })
            comp_resp.raise_for_status()
            comp = comp_resp.json()
            agents_used.append("compliance_checker")
            token_usage["total_input"] += comp["prompt_tokens"]
            token_usage["total_output"] += comp["completion_tokens"]
            logger.info(f"Compliance: {comp['status']} in {comp['response_time_ms']}ms")

            # Step 4: Risk
            logger.info("Calling Risk Service (port 8004)...")
            risk_resp = await client.post(f"{RISK_URL}/assess", json={
                "question": question,
                "compliance_status": comp["status"],
                "reasoning": comp["reasoning"],
                "violated_policies": comp["violated_policies"]
            })
            risk_resp.raise_for_status()
            risk = risk_resp.json()
            agents_used.append("risk_assessment")
            token_usage["total_input"] += risk["prompt_tokens"]
            token_usage["total_output"] += risk["completion_tokens"]
            logger.info(f"Risk: {risk['risk_level']} ({risk['risk_score']:.2f}) in {risk['response_time_ms']}ms")

            # Step 5: Recommendation
            logger.info("Calling Recommendation Service (port 8005)...")
            rec_resp = await client.post(f"{RECOMMENDATION_URL}/recommend", json={
                "question": question,
                "compliance_status": comp["status"],
                "risk_level": risk["risk_level"],
                "risk_factors": risk["risk_factors"],
                "urgency": risk["urgency"],
                "violated_policies": comp["violated_policies"],
                "applicable_sections": interp["applicable_sections"]
            })
            rec_resp.raise_for_status()
            rec = rec_resp.json()
            agents_used.append("recommendation")
            token_usage["total_input"] += rec["prompt_tokens"]
            token_usage["total_output"] += rec["completion_tokens"]
            logger.info(f"Recommendation complete in {rec['response_time_ms']}ms")

        except Exception as e:
            logger.warning(f"GPT-4o pipeline failed, activating retrieval fallback: {e}")
            use_fallback = True

    # Build final response
    token_usage["total"] = token_usage["total_input"] + token_usage["total_output"]
    elapsed_ms = (time.time() - start_time) * 1000
    citations = _build_citations(chunks)

    if use_fallback:
        # Fallback response - retrieval only, no GPT-4o
        logger.info("Returning fallback retrieval-only response")
        policy_sections = "\n\n".join([
            f"- {c.get('metadata', {}).get('source', 'Policy Document')} "
            f"[{c.get('metadata', {}).get('subcategory', 'General')}]: "
            f"{c['text'][:300]}..."
            for c in chunks[:3]
        ])

        analytics.record_query(
            question=question,
            risk_level="UNKNOWN",
            compliance_status="REQUIRES_REVIEW",
            nist_functions_hit=ret.get("frameworks", []),
            response_time_ms=elapsed_ms,
            token_count=0
        )

        return {
            "success": True,
            "question": question,
            "answer": (
                "AI reasoning is temporarily unavailable. "
                "Based on policy retrieval, here are the most relevant sections:\n\n"
                f"{policy_sections}\n\n"
                "Please consult these sections directly or contact your compliance team for guidance."
            ),
            "interpretation": "Retrieval-only mode - AI reasoning temporarily unavailable.",
            "compliance_status": "REQUIRES_REVIEW",
            "compliance_reasoning": "Manual review required - AI pipeline temporarily unavailable.",
            "violated_policies": [],
            "conflicts_detected": False,
            "conflict_details": "",
            "risk_level": "UNKNOWN",
            "risk_score": 0.0,
            "risk_factors": [],
            "potential_consequences": [],
            "urgency": "MANUAL_REVIEW",
            "next_steps": [
                "Review the retrieved policy sections above",
                "Consult your compliance team for a definitive answer",
                "Refer to the cited NIST policy sections directly"
            ],
            "escalation_required": False,
            "escalation_path": "",
            "compliant_alternative": "",
            "citations": citations,
            "agents_used": agents_used,
            "token_usage": token_usage,
            "response_time_ms": round(elapsed_ms, 1),
            "frameworks": ret.get("frameworks", []),
            "architecture": "microservices",
        }

    # Full pipeline response - normal path
    analytics.record_query(
        question=question,
        risk_level=risk["risk_level"],
        compliance_status=comp["status"],
        nist_functions_hit=ret["frameworks"],
        response_time_ms=elapsed_ms,
        token_count=token_usage["total"]
    )

    logger.info(f"Query complete in {elapsed_ms:.1f}ms - status={comp['status']} risk={risk['risk_level']} tokens={token_usage['total']}")

    return {
        "success": True,
        "question": question,
        "answer": rec["summary"],
        "interpretation": interp["interpretation"],
        "compliance_status": comp["status"],
        "compliance_reasoning": comp["reasoning"],
        "violated_policies": comp["violated_policies"],
        "conflicts_detected": comp["conflicts_detected"],
        "conflict_details": comp.get("conflict_details", ""),
        "risk_level": risk["risk_level"],
        "risk_score": risk["risk_score"],
        "risk_factors": risk["risk_factors"],
        "potential_consequences": risk["potential_consequences"],
        "urgency": risk["urgency"],
        "next_steps": rec["next_steps"],
        "escalation_required": rec["escalation_required"],
        "escalation_path": rec["escalation_path"],
        "compliant_alternative": rec["compliant_alternative"],
        "citations": citations,
        "agents_used": agents_used,
        "token_usage": token_usage,
        "response_time_ms": round(elapsed_ms, 1),
        "frameworks": ret["frameworks"],
        "architecture": "microservices",
    }


@app.get("/api/v1/analytics")
async def get_analytics():
    logger.info("Analytics requested")
    return analytics.get_dashboard_data()


@app.get("/api/v1/services")
async def list_services():
    return {
        "services": [
            {"name": "retrieval",      "port": 8001, "endpoint": "/retrieve",  "description": "Hybrid BM25 + vector search"},
            {"name": "interpretation", "port": 8002, "endpoint": "/interpret",  "description": "Policy explanation (GPT-4o)"},
            {"name": "compliance",     "port": 8003, "endpoint": "/check",      "description": "Compliance determination (GPT-4o)"},
            {"name": "risk",           "port": 8004, "endpoint": "/assess",     "description": "Risk scoring 0.0-1.0 (GPT-4o)"},
            {"name": "recommendation", "port": 8005, "endpoint": "/recommend",  "description": "Next steps + escalation (GPT-4o)"},
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
