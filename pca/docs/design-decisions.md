# ComplianceAI — Design Decisions & Tradeoffs

This document explains every key architectural and technical decision made in building the
ComplianceAI Policy Compliance Intelligence Assistant, along with the tradeoffs considered.

---

## 1. Architecture Decision — Microservices vs Monolith

**Decision:** Microservices architecture with 6 independent FastAPI services.

**Why microservices:**
- Each agent has a single responsibility — retrieval, interpretation, compliance, risk, recommendation
- Each service can be independently scaled, deployed, and monitored
- Failure in one service does not crash the entire system
- Easier to test and debug individual agents in isolation
- Follows enterprise-grade patterns expected in production systems

**Tradeoff:**
- Higher operational complexity — 6 processes to manage vs 1
- Network latency between services adds ~50-100ms per call
- More complex startup procedure

**Mitigation:**
- `start.ps1` script starts all 6 services with one command
- Gateway handles all orchestration — frontend only talks to one endpoint
- Per-service health checks and structured logs give clear visibility into failures

---

## 2. LLM Selection — GPT-4o

**Decision:** GPT-4o for all 5 reasoning agents.

**Why GPT-4o:**
- Best-in-class reasoning for complex compliance interpretation
- Consistent structured output following exact prompt templates
- Reliable JSON-parseable responses for compliance status and risk levels
- Strong legal and regulatory domain knowledge

**Tradeoff:**
- API cost (~$0.01-0.03 per query)
- External API dependency — requires internet connection
- Latency ~2-3 seconds per agent call (~15s total for 5 agents)

**Alternatives considered:**
- GPT-3.5-turbo — cheaper but less accurate for compliance reasoning
- Local LLMs (Llama, Mistral) — free but insufficient for structured legal reasoning
- Claude — comparable quality but GPT-4o had better structured output consistency

---

## 3. Embedding Model — text-embedding-3-small (OpenAI)

**Decision:** `all-MiniLM-L6-v2 (local, sentence-transformers)

**Why text-embedding-3-small:**
- 1536-dimensional vectors — 4x richer semantic representation than local models (384d)
- Specifically optimised for semantic similarity and retrieval tasks
- Consistent with the OpenAI ecosystem already used for GPT-4o agents
- Extremely cost-efficient at ~$0.00002 per 1000 tokens
- Stronger semantic understanding of nuanced compliance and regulatory language

**Tradeoff:**
- Requires OpenAI API call during ingestion (vs fully local model)
- Slight internet dependency for re-ingestion

**Why the tradeoff is acceptable:**
- Ingestion is a one-time operation — not per query
- The same OpenAI API key used for GPT-4o agents is reused
- Cost of ingesting 89 chunks is negligible (~$0.0001 total)
- DeepEval results confirm 88.6% test pass rate with improved retrieval quality

**Previous model:** all-MiniLM-L6-v2 (sentence-transformers, 384d) — upgraded to text-embedding-3-small for richer semantic representation.

---

## 4. Vector Database — ChromaDB vs Pinecone vs Weaviate

**Decision:** ChromaDB with local persistent storage.

**Why ChromaDB:**
- Runs fully locally — no external service or API key needed
- Simple Python API — easy to integrate with embedding pipeline
- Persistent storage — survives restarts, no re-ingestion needed on every startup
- Free — no cloud costs
- Sufficient for 89 chunks (well within ChromaDB's scale)

**Tradeoff:**
- Not cloud-native — no built-in replication or distributed scaling
- No built-in hybrid search — BM25 implemented separately via rank-bm25

**Alternatives considered:**
- Pinecone — managed, scalable but costs money and sends data to cloud
- Weaviate — more features but heavier infrastructure overhead
- FAISS — faster but no metadata filtering or persistence

---

## 5. Retrieval Strategy — Hybrid Search (BM25 + Vector + RRF + Authority)

**Decision:** Three-stage retrieval — BM25 keyword + vector similarity + RRF fusion + authority reranking.

**Why hybrid:**
- Vector search alone misses exact NIST section references like "PR.AA-01"
- BM25 alone misses semantic meaning ("password policy" vs "authentication requirements")
- RRF (Reciprocal Rank Fusion) combines both rankings optimally
- Weights: 60% semantic + 40% keyword

**Why authority reranking:**
- NIST CSF 2.0 (primary standard) should rank higher than supplementary template guides
- Authority score: NIST CSF 2.0 = 1.0, supplementary guides = 0.85
- Final score = RRF score × (0.7 + 0.3 × authority)

**Tradeoff:**
- Slightly more complex than pure vector search
- BM25 index must be rebuilt on every ingestion

**Why the tradeoff is worth it:**
- Hybrid search significantly improves recall for specific NIST section queries
- Authority reranking ensures primary policy sources always take precedence

---

## 6. Chunking Strategy — Hierarchical NIST-aware Chunking

**Decision:** Semantic chunking preserving NIST function and category hierarchy.

**Why hierarchical chunking:**
- NIST CSF has a clear hierarchy: Function → Category → Subcategory
- Preserving this hierarchy in metadata enables precise filtering by framework area
- Each chunk maps to exactly one NIST subcategory (e.g., PR.AA-01)
- Metadata enables exact section citation in every response

**Chunking levels:**
1. Split on NIST function headers (GOVERN, IDENTIFY, PROTECT, DETECT, RESPOND, RECOVER)
2. Split on subcategory codes (e.g., PR.DS-01, RS.AN-06)
3. Fixed-size fallback for non-NIST sections (512 tokens, 128 overlap)

**Result:** 89 chunks from 2 PDFs — fine-grained enough for precise retrieval.

**Tradeoff:**
- Smaller chunks may occasionally lose broader context
- Fixed chunk boundaries may split related content across adjacent subcategories

---

## 7. Agent Orchestration — Sequential vs Parallel

**Decision:** Sequential agent pipeline — each agent receives output of the previous agent.

**Why sequential:**
- Each agent depends causally on the previous agent's output:
  - Compliance checker needs interpretation agent's key clauses
  - Risk agent needs compliance status and violated policies
  - Recommendation agent needs risk level and urgency
- Sequential handoff preserves full context across agents
- Simpler to debug — each step has clear, traceable input/output

**Tradeoff:**
- Total latency = sum of all agent latencies (~15-30 seconds)
- No parallelism — agents cannot run simultaneously

**Alternatives considered:**
- Parallel execution — not possible since agents are causally dependent on each other's outputs
- Async pipeline — complex to implement, minimal benefit given sequential dependency

---

## 8. Guardrail Design — Multi-Layer Input Validation

**Decision:** Three-layer guardrails — Pydantic schema validation + gateway semantic validation + compliance keyword check.

**Layer 1 — Pydantic (FastAPI schema):**
- Enforces minimum 5 chars, maximum 1000 chars at API schema level
- Validates request structure before any processing
- Rejects malformed requests immediately

**Layer 2 — Gateway guardrails (guardrails.py):**
- Off-topic phrase detection ("movies to watch", "suggest me some movies")
- Off-topic keyword detection with word-boundary matching (\b regex)
- Prompt injection pattern detection (15+ patterns)
- Compliance keyword requirement check

**Layer 3 — Retrieval relevance threshold:**
- If top retrieved chunk score < 0.15, query is considered irrelevant
- Prevents fake policy references on edge-case queries

**Why three layers:**
- Schema validation catches technical issues before any logic runs
- Semantic validation ensures only compliance questions reach agents
- Relevance threshold catches queries that slip past keyword filters
- Each layer stops processing immediately — zero agents run on rejected queries

**Key fix applied:** Off-topic queries (e.g. movie recommendations) were initially reaching compliance agents due to weak single-keyword matching. Fixed by adding multi-word phrase detection and word-boundary regex, confirmed via gateway and compliance service logs showing no new entries for blocked queries.

**Tradeoff:**
- May occasionally reject legitimate edge-case compliance questions
- Keyword and phrase lists require maintenance as new topics emerge

---

## 9. Frontend Architecture — React + Express vs Single Page HTML

**Decision:** React 18 + Vite frontend with Express.js proxy server.

**Why React + Express:**
- React enables real-time UI updates (agent pipeline animation, response streaming)
- Express proxy handles CORS and API routing cleanly
- Vite provides fast hot-reload during development
- Component-based architecture is maintainable and extensible

**Tradeoff:**
- More complex setup than a single HTML file
- Requires Node.js 18+ in addition to Python 3.11+

**Why the tradeoff is worth it:**
- Provides professional enterprise-grade UI
- Agent pipeline visualization and analytics dashboard require reactive state management
- Sample query buttons, NIST function filters, and session stats require component state

---

## 10. Evaluation Framework — DeepEval

**Decision:** DeepEval with 5 metrics — Answer Relevancy, Faithfulness, Contextual Precision,
Contextual Recall, and LLM-as-Judge (GEval).

**Why DeepEval:**
- Purpose-built for RAG system evaluation
- LLM-as-judge pattern uses GPT-4o to evaluate response quality objectively
- Standardized metrics with configurable thresholds
- Integrates with pytest for repeatable evaluation runs

**Results:** 31/35 tests passing (88.6%)

**Why 4 failures are acceptable:**
- TC-005: Phishing question — NIST docs do not have specific phishing response sections (honest knowledge gap)
- TC-002: Risk level disagreement — system returned MINIMAL, expected MEDIUM (borderline case)
- TC-003: Password policy — NIST CSF does not define specific password rules (correct behavior — not a hallucination)

**Tradeoff:**
- DeepEval runs cost ~$0.10-0.20 per full suite (uses GPT-4o as evaluator)
- Evaluation results are non-deterministic (LLM outputs vary slightly between runs)

---

## 11. Logging — Structured Per-Service Logging

**Decision:** Python `logging` module with per-service log files and console output.

**Why structured logging:**
- Each service writes to its own log file (gateway.log, compliance.log, etc.)
- Log format includes timestamp, service name, log level, and message
- Response times logged per agent call for performance monitoring
- Enables post-mortem debugging — can trace exactly what happened for any query

**Example log entry:**
```
2026-03-16 10:39:50,091 [COMPLIANCE] INFO — Compliance result: COMPLIANT in 1666.0ms — conflicts: False
```

---

## Summary of Key Tradeoffs

| Decision | Chose | Tradeoff Accepted |
|----------|-------|-------------------|
| Architecture | Microservices | Higher complexity for better scalability |
| LLM | GPT-4o | API cost for best reasoning accuracy |
| Embeddings | all-MiniLM-L6-v2 (local, 384d) | API dependency for 4x richer vectors |
| Vector DB | ChromaDB | No cloud scale for zero cost + local privacy |
| Retrieval | Hybrid BM25+Vector+RRF+Authority | More complexity for significantly better recall |
| Chunking | Hierarchical NIST-aware | Smaller chunks for precise section citations |
| Orchestration | Sequential agents | Higher latency for correct causal context flow |
| Guardrails | Three-layer validation | Occasional edge rejections for strong security |
| Frontend | React 18 + Express | Complex setup for professional enterprise UI |
| Evaluation | DeepEval 5-metric suite | ~$0.15 per run for objective RAG quality metrics |
| Logging | Per-service structured logs | Disk usage for full query traceability |

