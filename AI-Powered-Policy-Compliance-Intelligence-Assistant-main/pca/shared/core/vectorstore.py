"""
ChromaDB vector store with hybrid BM25 + semantic search via RRF fusion
and authority-based reranking.
"""

import os
from typing import Optional
import chromadb
from chromadb.config import Settings
from rank_bm25 import BM25Okapi
from shared.core.chunker import PolicyChunk
from shared.core.embeddings import embed_texts, embed_query

# Authority scores — higher = more authoritative source
AUTHORITY_SCORES = {
    "nist csf 2.0": 1.0,
    "nist cybersecurity framework": 0.85,
    "cybersecurity-framework": 0.85,
    "nist": 0.80,
}


class PolicyVectorStore:
    def __init__(self, persist_dir: Optional[str] = None, collection_name: Optional[str] = None):
        self.persist_dir = persist_dir or os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
        self.collection_name = collection_name or os.getenv("CHROMA_COLLECTION_NAME", "policy_documents")
        self._client = None
        self._collection = None
        self._bm25_index = None
        self._bm25_docs: list = []
        self._bm25_ids: list = []

    @property
    def client(self):
        if self._client is None:
            self._client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=Settings(anonymized_telemetry=False),
            )
        return self._client

    @property
    def collection(self):
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def add_chunks(self, chunks: list, batch_size: int = 100) -> int:
        print(f"[VectorStore] Ingesting {len(chunks)} chunks...")
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i: i + batch_size]
            ids = [c.chunk_id for c in batch]
            texts = [c.text for c in batch]
            embeddings = embed_texts(texts)
            metadatas = [{
                "source": c.source, "framework": c.framework,
                "nist_function": c.nist_function or "",
                "category": c.category or "",
                "subcategory": c.subcategory or "",
                "page_number": c.page_number or -1,
            } for c in batch]
            self.collection.upsert(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
            print(f"[VectorStore] Ingested batch {i // batch_size + 1}")
        self._rebuild_bm25_index()
        total = self.collection.count()
        print(f"[VectorStore] Total documents: {total}")
        return total

    def _rebuild_bm25_index(self):
        results = self.collection.get(include=["documents"])
        self._bm25_docs = results["documents"]
        self._bm25_ids = results["ids"]
        if self._bm25_docs:
            tokenized = [doc.lower().split() for doc in self._bm25_docs]
            self._bm25_index = BM25Okapi(tokenized)
            print(f"[VectorStore] BM25 index rebuilt with {len(self._bm25_docs)} docs")

    def _get_authority_score(self, meta: dict) -> float:
        """Return authority score based on source document."""
        source = meta.get("source", "").lower()
        for key, score in AUTHORITY_SCORES.items():
            if key in source:
                return score
        return 0.7  # default authority for unknown sources

    def hybrid_search(self, query: str, top_k: int = 5, filters: Optional[dict] = None,
                      semantic_weight: float = 0.6, keyword_weight: float = 0.4) -> list:
        total = self.collection.count()
        if total == 0:
            return []

        query_embedding = embed_query(query)
        where_clause = _build_where_clause(filters)

        n_results = min(top_k * 3, total)
        semantic_results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where_clause if where_clause else None,
            include=["documents", "metadatas", "distances"],
        )

        semantic_ids = semantic_results["ids"][0]
        semantic_docs = semantic_results["documents"][0]
        semantic_metas = semantic_results["metadatas"][0]
        semantic_ranks = {doc_id: rank for rank, doc_id in enumerate(semantic_ids)}

        bm25_ranks = {}
        if self._bm25_index and self._bm25_docs:
            bm25_scores = self._bm25_index.get_scores(query.lower().split())
            bm25_ranked = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)
            for rank, idx in enumerate(bm25_ranked[:top_k * 3]):
                bm25_ranks[self._bm25_ids[idx]] = rank

        all_ids = set(semantic_ranks.keys()) | set(bm25_ranks.keys())
        rrf_scores = {}
        for doc_id in all_ids:
            sem_r = semantic_ranks.get(doc_id, top_k * 3)
            kw_r = bm25_ranks.get(doc_id, top_k * 3)
            rrf_scores[doc_id] = semantic_weight / (60 + sem_r) + keyword_weight / (60 + kw_r)

        top_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)[:top_k]
        id_to_data = {doc_id: (doc, meta) for doc_id, doc, meta in zip(semantic_ids, semantic_docs, semantic_metas)}

        bm25_only = [i for i in top_ids if i not in id_to_data]
        if bm25_only:
            extra = self.collection.get(ids=bm25_only, include=["documents", "metadatas"])
            for eid, edoc, emeta in zip(extra["ids"], extra["documents"], extra["metadatas"]):
                id_to_data[eid] = (edoc, emeta)

        # Authority-based reranking
        # Final score = RRF relevance score * authority weight
        final = []
        for doc_id in top_ids:
            if doc_id in id_to_data:
                doc, meta = id_to_data[doc_id]
                authority = self._get_authority_score(meta)
                final_score = rrf_scores[doc_id] * (0.7 + 0.3 * authority)
                final.append({
                    "id": doc_id,
                    "text": doc,
                    "metadata": meta,
                    "score": round(final_score, 6),
                    "authority_score": authority,
                    "rrf_score": round(rrf_scores[doc_id], 6),
                })

        # Sort by final score — most relevant + most authoritative first
        final.sort(key=lambda x: x["score"], reverse=True)
        return final

    def count(self) -> int:
        return self.collection.count()

    def reset(self):
        self.client.delete_collection(self.collection_name)
        self._collection = None
        self._bm25_index = None
        self._bm25_docs = []
        self._bm25_ids = []


def _build_where_clause(filters: Optional[dict]) -> Optional[dict]:
    if not filters:
        return None
    conditions = []
    if filters.get("framework"):
        conditions.append({"framework": {"$eq": filters["framework"]}})
    if filters.get("nist_function"):
        conditions.append({"nist_function": {"$eq": filters["nist_function"].upper()}})
    if filters.get("category"):
        conditions.append({"category": {"$eq": filters["category"]}})
    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}