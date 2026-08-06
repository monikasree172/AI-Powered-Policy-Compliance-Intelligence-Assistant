"""
Orchestrator — coordinates all 5 agents sequentially.
"""

import os
import time
from typing import Optional
from openai import OpenAI

from shared.core.vectorstore import PolicyVectorStore
from shared.core.guardrails import validate_query
from shared.agents.retrieval_agent import PolicyRetrievalAgent
from shared.agents.interpretation_agent import PolicyInterpretationAgent
from shared.agents.compliance_agent import ComplianceCheckerAgent
from shared.agents.risk_agent import RiskAssessmentAgent
from shared.agents.recommendation_agent import RecommendationAgent
from shared.utils.token_tracker import TokenTracker
from shared.utils.analytics import analytics


class ComplianceOrchestrator:
    def __init__(self, vector_store: PolicyVectorStore, openai_api_key: str):
        self.vector_store = vector_store
        self.client = OpenAI(api_key=openai_api_key)
        self.retrieval_agent = PolicyRetrievalAgent(vector_store)
        self.interpretation_agent = PolicyInterpretationAgent(self.client)
        self.compliance_agent = ComplianceCheckerAgent(self.client)
        self.risk_agent = RiskAssessmentAgent(self.client)
        self.recommendation_agent = RecommendationAgent(self.client)

    def process_query(self, question: str, context: Optional[dict] = None,
                      filters: Optional[dict] = None) -> dict:
        start_time = time.time()
        tracker = TokenTracker()

        # Step 0: Guardrails
        guard = validate_query(question)
        if not guard.is_valid:
            return {"success": False, "error": guard.reason, "question": question}

        q = guard.sanitized_query
        agents_used = []

        # Step 1: Retrieval
        ret = self.retrieval_agent.run(query=q, top_k=5, filters=filters, tracker=tracker)
        agents_used.append("retrieval")
        if ret.get("error"):
            return {"success": False, "error": ret["error"], "question": q}

        chunks = ret["chunks"]

        # Step 2: Interpretation
        interp = self.interpretation_agent.run(question=q, retrieved_chunks=chunks, tracker=tracker)
        agents_used.append("interpretation")

        # Step 3: Compliance Check
        comp = self.compliance_agent.run(
            question=q, interpretation=interp["interpretation"],
            key_clauses=interp["key_clauses"], retrieved_chunks=chunks, tracker=tracker)
        agents_used.append("compliance_checker")

        # Step 4: Risk Assessment
        risk = self.risk_agent.run(
            question=q, compliance_status=comp["status"],
            reasoning=comp["reasoning"], violated_policies=comp["violated_policies"],
            tracker=tracker)
        agents_used.append("risk_assessment")

        # Step 5: Recommendation
        rec = self.recommendation_agent.run(
            question=q, compliance_status=comp["status"],
            risk_level=risk["risk_level"], risk_factors=risk["risk_factors"],
            urgency=risk["urgency"], violated_policies=comp["violated_policies"],
            applicable_sections=interp["applicable_sections"], tracker=tracker)
        agents_used.append("recommendation")

        citations = _build_citations(chunks, rec["citations"])
        token_totals = tracker.totals()
        elapsed_ms = (time.time() - start_time) * 1000

        analytics.record_query(
            question=q, risk_level=risk["risk_level"],
            compliance_status=comp["status"],
            nist_functions_hit=ret["nist_functions"],
            response_time_ms=elapsed_ms, token_count=token_totals["total"])

        return {
            "success": True,
            "question": q,
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
            "token_usage": token_totals,
            "response_time_ms": round(elapsed_ms, 1),
            "frameworks": ret["frameworks"],
        }


def _build_citations(chunks: list, section_refs: list) -> list:
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
