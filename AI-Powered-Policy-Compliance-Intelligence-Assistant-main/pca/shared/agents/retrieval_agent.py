"""Policy Retrieval Agent — hybrid semantic + BM25 search, no LLM needed."""

from typing import Optional
from shared.core.vectorstore import PolicyVectorStore
from shared.utils.token_tracker import TokenTracker


class PolicyRetrievalAgent:
    def __init__(self, vector_store: PolicyVectorStore):
        self.vector_store = vector_store
        self.name = "retrieval"

    def run(self, query: str, top_k: int = 5, filters: Optional[dict] = None,
            tracker: Optional[TokenTracker] = None) -> dict:
        if self.vector_store.count() == 0:
            return {
                "chunks": [], "query": query, "total_found": 0,
                "frameworks": [], "nist_functions": [],
                "error": "No policy documents ingested. Run: python scripts/ingest.py",
            }

        chunks = self.vector_store.hybrid_search(query=query, top_k=top_k, filters=filters)
        frameworks = list({c["metadata"].get("framework", "") for c in chunks if c["metadata"].get("framework")})
        nist_functions = list({c["metadata"].get("nist_function", "") for c in chunks if c["metadata"].get("nist_function")})

        return {
            "chunks": chunks, "query": query, "total_found": len(chunks),
            "frameworks": frameworks, "nist_functions": nist_functions,
        }
