"""
Retrieval Microservice — Port 8001
Handles hybrid semantic + BM25 search against ChromaDB
"""

import os
import sys
import logging
import time
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [RETRIEVAL] %(levelname)s — %(message)s",
    handlers=[
        logging.FileHandler("logs/retrieval.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("retrieval")

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from shared.core.vectorstore import PolicyVectorStore

app = FastAPI(title="Retrieval Service", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_vector_store: Optional[PolicyVectorStore] = None


@app.on_event("startup")
def startup():
    global _vector_store
    logger.info("Starting Retrieval Service...")
    _vector_store = PolicyVectorStore()
    logger.info(f"VectorStore ready — {_vector_store.count()} documents indexed")


class RetrievalRequest(BaseModel):
    query: str
    top_k: int = 5
    filters: Optional[dict] = None


class RetrievalResponse(BaseModel):
    chunks: list
    query: str
    total_found: int
    frameworks: list
    nist_functions: list
    response_time_ms: float


@app.get("/health")
def health():
    count = _vector_store.count() if _vector_store else 0
    logger.info(f"Health check — {count} docs indexed")
    return {"status": "healthy", "service": "retrieval", "port": 8001, "documents_indexed": count}


@app.post("/retrieve", response_model=RetrievalResponse)
def retrieve(request: RetrievalRequest):
    start = time.time()
    logger.info(f"Retrieval request — query: '{request.query[:80]}' top_k={request.top_k}")

    if not _vector_store or _vector_store.count() == 0:
        logger.error("No documents ingested in vector store")
        raise HTTPException(status_code=503, detail="No policy documents ingested. Run: python scripts/ingest.py")

    try:
        chunks = _vector_store.hybrid_search(query=request.query, top_k=request.top_k, filters=request.filters)
        frameworks = list({c["metadata"].get("framework", "") for c in chunks if c["metadata"].get("framework")})
        nist_functions = list({c["metadata"].get("nist_function", "") for c in chunks if c["metadata"].get("nist_function")})
        elapsed = (time.time() - start) * 1000
        logger.info(f"Retrieved {len(chunks)} chunks in {elapsed:.1f}ms — frameworks: {frameworks}")
        return RetrievalResponse(
            chunks=chunks, query=request.query,
            total_found=len(chunks), frameworks=frameworks,
            nist_functions=nist_functions, response_time_ms=round(elapsed, 1)
        )
    except Exception as e:
        logger.error(f"Retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
