"""
Performance Benchmarking across Policy Frameworks
Run: python tests/test_benchmark.py
"""
import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from dotenv import load_dotenv
load_dotenv()
from shared.core.vectorstore import PolicyVectorStore
from shared.agents.orchestrator import ComplianceOrchestrator

BENCHMARK_QUERIES = [
    {"query": "What are the password requirements?", "framework": "NIST"},
    {"query": "Can I share customer data with a vendor?", "framework": "NIST"},
    {"query": "Should I report a data breach immediately?", "framework": "NIST"},
    {"query": "Are there restrictions on cross-region data transfers?", "framework": "GDPR"},
    {"query": "What is required for remote access security?", "framework": "NIST"},
]

def run_benchmark():
    api_key = os.getenv("OPENAI_API_KEY")
    vs = PolicyVectorStore()
    orchestrator = ComplianceOrchestrator(vector_store=vs, openai_api_key=api_key)

    print("\n" + "="*60)
    print("PERFORMANCE BENCHMARK — Policy Compliance System")
    print("="*60)

    results = []
    for i, q in enumerate(BENCHMARK_QUERIES, 1):
        print(f"\n[{i}/5] Framework: {q['framework']}")
        print(f"Query: {q['query']}")
        start = time.time()
        result = orchestrator.process_query(question=q["query"])
        elapsed = (time.time() - start) * 1000
        results.append({
            "framework": q["framework"],
            "response_time_ms": elapsed,
            "tokens": result.get("token_usage", {}).get("total", 0),
            "risk_level": result.get("risk_level"),
            "compliance_status": result.get("compliance_status"),
        })
        print(f"✅ {elapsed:.0f}ms | {results[-1]['tokens']} tokens | {results[-1]['risk_level']} | {results[-1]['compliance_status']}")

    print("\n" + "="*60)
    print("BENCHMARK SUMMARY")
    print("="*60)
    frameworks = list(set(r["framework"] for r in results))
    for fw in frameworks:
        fw_results = [r for r in results if r["framework"] == fw]
        avg_time = sum(r["response_time_ms"] for r in fw_results) / len(fw_results)
        avg_tokens = sum(r["tokens"] for r in fw_results) / len(fw_results)
        print(f"\nFramework: {fw}")
        print(f"  Queries run:      {len(fw_results)}")
        print(f"  Avg response time: {avg_time:.0f}ms")
        print(f"  Avg tokens used:   {avg_tokens:.0f}")

    total_avg = sum(r["response_time_ms"] for r in results) / len(results)
    print(f"\nOverall avg response time: {total_avg:.0f}ms")
    print(f"Total queries benchmarked: {len(results)}")
    print("="*60)

if __name__ == "__main__":
    run_benchmark()