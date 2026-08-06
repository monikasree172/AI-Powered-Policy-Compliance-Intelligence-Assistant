# ComplianceAI – Policy Compliance Intelligence Assistant

AI-powered multi-agent RAG system for enterprise policy compliance queries.
Built with microservices architecture – 6 independent FastAPI services orchestrated via API Gateway.

---

## Architecture Overview
```
User → React UI → Vite Proxy → API Gateway (8000)
                                        ↓
                    ┌───────────────────────────────────┐
                    │        Microservices Pipeline      │
                    │                                   │
                    │  Retrieval      (port 8001)       │
                    │  Interpretation (port 8002)       │
                    │  Compliance     (port 8003)       │
                    │  Risk           (port 8004)       │
                    │  Recommendation (port 8005)       │
                    └───────────────────────────────────┘
                                        ↓
                              ChromaDB Vector Store
                              (89 NIST policy chunks)
```

---

## Project Structure
```
pca/
├── services/                    ← 6 independent microservices
│   ├── gateway/                 ← API Gateway (port 8000)
│   ├── retrieval/               ← Hybrid BM25 + vector search (port 8001)
│   ├── interpretation/          ← Policy explanation GPT-4o (port 8002)
│   ├── compliance/              ← Compliance checker GPT-4o (port 8003)
│   ├── risk/                    ← Risk scoring 0.0-1.0 GPT-4o (port 8004)
│   ├── recommendation/          ← Next steps + escalation GPT-4o (port 8005)
│   └── docker-compose.yml
├── shared/                      ← Shared code across services
│   ├── agents/                  ← Agent class implementations
│   ├── core/                    ← vectorstore, embeddings, chunker, guardrails
│   └── utils/                   ← analytics, token_tracker
├── frontend/                    ← React 18 + Vite UI
│   └── client/                  ← React + Vite (port 3000)
├── tests/                       ← DeepEval + API tests
├── docs/                        ← NIST PDF documents
├── scripts/                     ← Document ingestion
├── logs/                        ← Service logs (6 files)
├── chroma_db/                   ← Vector database
├── start.ps1                    ← One-click startup script
├── .env                         ← API keys (never commit)
├── .env.example                 ← Template
└── requirements.txt
```

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- OpenAI API key

### Step 1 – Install dependencies
```bash
pip install -r requirements.txt
```

### Step 2 – Configure API key
```bash
cp .env.example .env
# Edit .env and set: OPENAI_API_KEY=sk-proj-...
```

### Step 3 – Ingest policy documents
```bash
python scripts/ingest.py --file "docs/nist-csf.pdf"
python scripts/ingest.py --file "docs/cybersecurity-framework.pdf"
# Result: 89 chunks indexed in ChromaDB
```

### Step 4 – Start all 6 microservices
```powershell
# Windows – one command starts all services
cd C:\path\to\pca_fixed_1\pca
powershell -ExecutionPolicy Bypass -File start.ps1
```

Or start individually:
```powershell
python -m uvicorn services.retrieval.main:app --port 8001
python -m uvicorn services.interpretation.main:app --port 8002
python -m uvicorn services.compliance.main:app --port 8003
python -m uvicorn services.risk.main:app --port 8004
python -m uvicorn services.recommendation.main:app --port 8005
python -m uvicorn services.gateway.main:app --port 8000
```

### Step 5 – Start frontend
```powershell
cd C:\path\to\pca_fixed_1\pca\frontend\client
npm install
npm run dev
# Opens http://localhost:3000
```

---

## Microservices

| Service | Port | Endpoint | Description |
|---------|------|----------|-------------|
| API Gateway | 8000 | POST /api/v1/query | Orchestrates all services |
| Retrieval | 8001 | POST /retrieve | Hybrid BM25 + vector search |
| Interpretation | 8002 | POST /interpret | Policy explanation (GPT-4o) |
| Compliance | 8003 | POST /check | Compliance determination (GPT-4o) |
| Risk | 8004 | POST /assess | Risk scoring 0.0-1.0 (GPT-4o) |
| Recommendation | 8005 | POST /recommend | Next steps + escalation (GPT-4o) |

### Verify all services healthy
```bash
curl http://localhost:8000/api/v1/health
# Returns: { "status": "healthy", "architecture": "microservices", "documents_indexed": 89 }
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/health | Health check – all service status |
| POST | /api/v1/query | Submit compliance question |
| GET | /api/v1/analytics | Analytics dashboard data |
| GET | /api/v1/services | List all microservices |

### Example Query
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Should I report accidental access to data that does not belong to my project?"}'
```

### Example Response
```json
{
  "success": true,
  "compliance_status": "COMPLIANT",
  "risk_level": "MINIMAL",
  "risk_score": 0.10,
  "answer": "You should report the accidental access immediately...",
  "next_steps": ["Document the incident", "Report to manager", "Follow IR procedures"],
  "citations": [{ "source": "NIST CSF 2.0", "section": "RS.AN-06" }],
  "agents_used": ["retrieval", "interpretation", "compliance_checker", "risk_assessment", "recommendation"],
  "token_usage": { "total": 1914 },
  "response_time_ms": 26894,
  "architecture": "microservices"
}
```

---

## Running Tests
```bash
# API tests
python -m pytest tests/test_api.py -v

# DeepEval evaluation suite
python -m pytest tests/test_deepeval.py -v
# Result: 32/35 tests passing (91.4%)
```

### DeepEval Metrics

| Metric | Threshold | Result |
|--------|-----------|--------|
| Answer Relevancy | ≥ 0.7 | 4/5 PASS |
| Faithfulness | ≥ 0.7 | 5/5 PASS |
| Contextual Precision | ≥ 0.6 | 4/5 PASS |
| Contextual Recall | ≥ 0.5 | 4/5 PASS |
| LLM-as-Judge (GEval) | ≥ 0.6 | 5/5 PASS |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | GPT-4o (OpenAI) |
| Embeddings | all-MiniLM-L6-v2 (local, sentence-transformers) |
| Vector Store | ChromaDB |
| Retrieval | BM25 + Vector + RRF fusion + Authority reranking |
| Backend | FastAPI (Python 3.11) |
| Frontend | React 18 + Vite |
| Evaluation | DeepEval |
| Architecture | Microservices (6 services) |

---

## Dataset

**NIST Cybersecurity Framework Policy Documents**
- `docs/nist-csf.pdf` – NIST CSF 2.0 core framework
- `docs/cybersecurity-framework.pdf` – CIS/MS-ISAC Policy Template Guide 2024
- Total: 89 semantic chunks indexed

---

## Compliance Statuses

| Status | Meaning |
|--------|---------|
| COMPLIANT | Action is clearly permitted |
| NON_COMPLIANT | Action clearly violates policy |
| REQUIRES_REVIEW | Gray area – needs human approval |
| INSUFFICIENT_INFO | Not enough context to decide |

---

## Risk Levels

| Level | Score | Urgency |
|-------|-------|---------|
| CRITICAL | 0.85-1.0 | IMMEDIATE |
| HIGH | 0.65-0.84 | WITHIN_24H |
| MEDIUM | 0.40-0.64 | WITHIN_WEEK |
| LOW | 0.20-0.39 | ROUTINE |
| MINIMAL | 0.0-0.19 | ROUTINE |