"""
DeepEval Test Suite
Run with: python -m pytest backend/tests/test_deepeval.py -v

Metrics: Answer Relevancy, Faithfulness, Contextual Precision,
         Contextual Recall, LLM-as-Judge, Risk/Status accuracy
"""

import os
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from dotenv import load_dotenv
load_dotenv()

from deepeval import evaluate
from deepeval.metrics import (
    AnswerRelevancyMetric,
    FaithfulnessMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    GEval,
)
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from shared.core.vectorstore import PolicyVectorStore
from shared.agents.orchestrator import ComplianceOrchestrator


TEST_CASES = [
    {
        "id": "TC-001",
        "question": "Can I share customer data with a third-party vendor without a data processing agreement?",
        "expected_keywords": ["data processing agreement", "third-party", "consent", "PR.DS"],
        "expected_status_options": ["NON_COMPLIANT"],
        "expected_risk_levels": ["HIGH", "CRITICAL"],
    },
    {
        "id": "TC-002",
        "question": "I accidentally saw data that does not belong to my project. Should I report it?",
        "expected_keywords": ["report", "incident", "notify", "DE.AE", "RS.AN"],
        "expected_status_options": ["COMPLIANT"],
        "expected_risk_levels": ["MEDIUM", "HIGH","MINIMAL"],
    },
    {
        "id": "TC-003",
        "question": "What are the password requirements for accessing internal systems?",
        "expected_keywords": ["password", "authentication", "PR.AC", "MFA"],
        "expected_status_options": ["COMPLIANT", "INSUFFICIENT_INFO"],
        "expected_risk_levels": ["LOW", "MEDIUM", "MINIMAL","INSUFFICIENT INFO"],
    },
    {
        "id": "TC-004",
        "question": "Are there restrictions when sharing customer data across different regions with another team?",
        "expected_keywords": ["data transfer", "GDPR", "privacy", "PR.DS"],
        "expected_status_options": ["NON_COMPLIANT", "REQUIRES_REVIEW"],
        "expected_risk_levels": ["HIGH", "CRITICAL", "MEDIUM"],
    },
    {
        "id": "TC-005",
        "question": "What should I do if I receive a suspicious phishing email?",
        "expected_keywords": ["report", "phishing", "incident", "DE.CM", "RS.CO"],
        "expected_status_options": ["COMPLIANT"],
        "expected_risk_levels": ["MEDIUM", "HIGH", "MINIMAL", "INSUFFICIENT_INFO"],
    },
]


@pytest.fixture(scope="module")
def orchestrator():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY not set")
    vs = PolicyVectorStore()
    if vs.count() == 0:
        pytest.skip("No documents ingested. Run: python scripts/ingest.py")
    return ComplianceOrchestrator(vector_store=vs, openai_api_key=api_key)


def _run_and_build(orchestrator, test_data: dict) -> LLMTestCase:
    result = orchestrator.process_query(question=test_data["question"])
    assert result.get("success"), f"Query failed: {result.get('error')}"
    retrieval_context = [
        f"{c['source']} {c['section']}: {c['text_excerpt']}"
        for c in result.get("citations", [])
    ]
    full_answer = f"{result['answer']}\n\nCompliance Status: {result['compliance_status']}\n"
    if result.get("next_steps"):
        full_answer += "\nNext Steps:\n" + "\n".join(f"- {s}" for s in result["next_steps"])
    if result.get("compliant_alternative"):
        full_answer += f"\n\nCompliant Alternative: {result['compliant_alternative']}"
    return LLMTestCase(
        input=test_data["question"],
        actual_output=full_answer,
        retrieval_context=retrieval_context,
        expected_output=f"Answer should address: {', '.join(test_data.get('expected_keywords', []))}",
        context=retrieval_context,
    )


@pytest.mark.parametrize("td", TEST_CASES, ids=[t["id"] for t in TEST_CASES])
def test_answer_relevancy(orchestrator, td):
    tc = _run_and_build(orchestrator, td)
    metric = AnswerRelevancyMetric(threshold=0.7, model="gpt-4o", include_reason=True)
    metric.measure(tc)
    print(f"\n[{td['id']}] Answer Relevancy: {metric.score:.3f} — {metric.reason}")
    assert metric.score >= 0.7


@pytest.mark.parametrize("td", TEST_CASES, ids=[t["id"] for t in TEST_CASES])
def test_faithfulness(orchestrator, td):
    tc = _run_and_build(orchestrator, td)
    metric = FaithfulnessMetric(threshold=0.7, model="gpt-4o", include_reason=True)
    metric.measure(tc)
    print(f"\n[{td['id']}] Faithfulness: {metric.score:.3f} — {metric.reason}")
    assert metric.score >= 0.7


@pytest.mark.parametrize("td", TEST_CASES, ids=[t["id"] for t in TEST_CASES])
def test_contextual_precision(orchestrator, td):
    tc = _run_and_build(orchestrator, td)
    if not tc.retrieval_context:
        pytest.skip("No retrieval context")
    metric = ContextualPrecisionMetric(threshold=0.6, model="gpt-4o", include_reason=True)
    metric.measure(tc)
    print(f"\n[{td['id']}] Contextual Precision: {metric.score:.3f}")
    assert metric.score >= 0.6


@pytest.mark.parametrize("td", TEST_CASES, ids=[t["id"] for t in TEST_CASES])
def test_contextual_recall(orchestrator, td):
    tc = _run_and_build(orchestrator, td)
    if not tc.retrieval_context:
        pytest.skip("No retrieval context")
    metric = ContextualRecallMetric(threshold=0.5, model="gpt-4o", include_reason=True)
    metric.measure(tc)
    print(f"\n[{td['id']}] Contextual Recall: {metric.score:.3f}")
    assert metric.score >= 0.5


@pytest.mark.parametrize("td", TEST_CASES, ids=[t["id"] for t in TEST_CASES])
def test_llm_judge_quality(orchestrator, td):
    tc = _run_and_build(orchestrator, td)
    metric = GEval(
        name="Compliance Interpretation Quality",
        criteria="""Evaluate whether the compliance response:
1. Clearly states whether the action is compliant or not
2. References specific policy sections or frameworks
3. Provides actionable next steps
4. Explains potential risks or consequences
5. Uses plain language understandable to a non-expert employee
Score 1 (lowest) if none met, 5 (highest) if all met.""",
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        threshold=0.6,
        model="gpt-4o",
    )
    metric.measure(tc)
    print(f"\n[{td['id']}] LLM-Judge: {metric.score:.3f} — {metric.reason}")
    assert metric.score >= 0.6


@pytest.mark.parametrize("td", TEST_CASES, ids=[t["id"] for t in TEST_CASES])
def test_risk_level(orchestrator, td):
    result = orchestrator.process_query(question=td["question"])
    assert result.get("success")
    actual = result.get("risk_level", "")
    expected = td.get("expected_risk_levels", [])
    print(f"\n[{td['id']}] Risk: {actual} (expected one of {expected})")
    if expected:
        assert actual in expected


@pytest.mark.parametrize("td", TEST_CASES, ids=[t["id"] for t in TEST_CASES])
def test_compliance_status(orchestrator, td):
    result = orchestrator.process_query(question=td["question"])
    assert result.get("success")
    actual = result.get("compliance_status", "")
    expected = td.get("expected_status_options", [])
    print(f"\n[{td['id']}] Status: {actual} (expected one of {expected})")
    if expected:
        assert actual in expected


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
