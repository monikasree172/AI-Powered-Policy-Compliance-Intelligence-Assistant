

---

# Complete Setup & Run Guide

---

## PREREQUISITES

### 1. Python 3.11+

```bash
python --version
```

### 2. Node.js 18+

```bash
node --version
```

### 3. OpenAI API Key

* Go to: [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)
* Create a new secret key
* Ensure your account has credits

---

## STEP-BY-STEP SETUP

### Step 1 — Open Terminal

* Windows: Win + R → type `cmd` → Enter
* Mac: Cmd + Space → type `terminal` → Enter
* Linux: Ctrl + Alt + T

---

### Step 2 — Navigate to Project Folder

```bash
cd path/to/pca

# Example (Windows)
cd C:\Users\YourName\Downloads\pca
```

---

### Step 3 — Create .env File

**Windows:**

```cmd
copy .env.example .env
notepad .env
```

**Mac/Linux:**

```bash
cp .env.example .env
nano .env
```

Add your API key:

```
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxx
```

Save and close.

---

### Step 4 — Install Dependencies

```bash
pip install -r requirements.txt
```

---

### Step 5 — Ingest Policy Documents

```bash
python scripts/ingest.py --file "docs/nist-csf.pdf"
python scripts/ingest.py --file "docs/cybersecurity-framework.pdf"
```

Expected output:

```
Ingestion complete. Total documents: 89
```

---

### Step 6 — Start Backend (Microservices)

**Recommended (single command):**

```powershell
powershell -ExecutionPolicy Bypass -File start.ps1
```

**Alternative (manual start in separate terminals):**

```bash
python -m uvicorn services.retrieval.main:app --port 8001
python -m uvicorn services.interpretation.main:app --port 8002
python -m uvicorn services.compliance.main:app --port 8003
python -m uvicorn services.risk.main:app --port 8004
python -m uvicorn services.recommendation.main:app --port 8005
python -m uvicorn services.gateway.main:app --port 8000
```

---

### Step 7 — Verify Backend

```bash
curl http://localhost:8000/api/v1/health
```

Expected response:

```json
{
  "status": "healthy",
  "architecture": "microservices",
  "documents_indexed": 89
}
```

---

### Step 8 — Start Frontend

Open a new terminal:

```bash
cd frontend/client
npm install
npm run dev
```

Open in browser:

```
http://localhost:3000
```

---

### Step 9 — Use the Application

1. Enter a compliance-related query
2. The API Gateway orchestrates all services
3. The system returns:

   * Compliance status
   * Risk level and score
   * Answer with citations
   * Recommended next steps

---

## TROUBLESHOOTING

| Problem                      | Fix                                               |
| ---------------------------- | ------------------------------------------------- |
| `/api/v1/health` returns 500 | Ensure all services (ports 8001–8005) are running |
| Chatbot not responding       | Check API Gateway (port 8000)                     |
| `OPENAI_API_KEY not set`     | Verify `.env` file                                |
| No documents found           | Run ingestion step again                          |
| Port already in use          | Change port or stop existing process              |
| Slow first run               | Normal (embedding model loads once)               |

---

## IMPORTANT NOTE

This is a microservices architecture:

* API Gateway (port 8000) depends on all services (8001–8005)
* If any service is not running, the system may return errors

---

## KEEP TERMINALS RUNNING

```
Terminal 1:
  Backend services (start.ps1)

Terminal 2:
  Frontend (npm run dev)
```

---
