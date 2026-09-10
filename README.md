# Executive COO Brain Backend API

A FastAPI backend for company intelligence and executive advisory capabilities. It connects directly to Supabase (`pgvector`), strictly enforces multi-tenant tenant isolation by extracting `company_id` from JWT claims, supports document ingestion with chunking (~500 tokens) & embedding (768-dim vector), captures institutional memory entries with automatic summary embedding, and features an executive COO chat endpoint (`POST /coo/chat`) that runs cosine similarity retrieval over pgvector, incorporates current goals and policies as structured context, and consults Ollama Cloud to deliver grounded advisory guidance with citations.

---

## Architecture Overview

```
coo_brain/
├── app/
│   ├── config.py             # Pydantic Settings (.env configuration)
│   ├── auth.py               # JWT company_id extraction & scoping guard
│   ├── database.py           # Supabase client factory (with RLS support)
│   ├── models/               # Exact Pydantic models for all tables (Create, Update, Read)
│   │   ├── company.py
│   │   ├── department.py
│   │   ├── employee.py
│   │   ├── goal.py
│   │   ├── policy.py
│   │   ├── document.py
│   │   ├── memory.py
│   │   └── chat.py
│   ├── services/
│   │   ├── chunking.py       # ~500 token chunker with paragraph/sentence overlap
│   │   ├── embedding.py      # Ollama Cloud async embedding service (nomic-embed-text)
│   │   ├── retrieval.py      # pgvector cosine similarity (<=>) RPC search & structured context
│   │   ├── llm.py            # Ollama Cloud chat service
│   │   └── brain.py          # Executive COO Chat orchestrator (advisory guardrail & citations)
│   ├── routers/
│   │   ├── companies.py      # Company endpoints
│   │   ├── departments.py    # Department CRUD
│   │   ├── employees.py      # Employee CRUD
│   │   ├── goals.py          # Goal CRUD
│   │   ├── policies.py       # Policy CRUD
│   │   ├── documents.py      # Document CRUD, chunking, and file upload
│   │   ├── memory.py         # Memory CRUD & POST /memory auto-embedding
│   │   └── coo.py            # POST /coo/chat & conversation history
│   └── main.py               # FastAPI app factory, CORS, and lifespan
├── sql/
│   ├── full_schema.sql       # Reference PostgreSQL schema
│   └── match_functions_and_delete_policies.sql
├── tests/                    # 23 automated tests across models, auth, chunking, and chat
├── .env.example
├── .env
├── requirements.txt
└── README.md
```

---

## Configuration & Environment Variables

Copy `.env.example` to `.env` and fill in your keys:

```bash
# Supabase Configuration
SUPABASE_URL=https://zhwulllprnbmbdkhhcol.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_JWT_SECRET=

# Ollama / LLM Configuration
OLLAMA_API_KEY=your_ollama_cloud_api_key_here
OLLAMA_BASE_URL=https://ollama.com/api
OLLAMA_CHAT_MODEL=llama3.3
OLLAMA_EMBED_MODEL=nomic-embed-text
OLLAMA_EMBED_BASE_URL=

# App Configuration
ENVIRONMENT=development
VECTOR_DIMENSION=768
TOP_K_DOCUMENTS=5
TOP_K_MEMORIES=5
```

> **Vector Dimension Alignment**:
> The `document_chunks` and `memory_entries` tables use `vector(768)`. Ollama's `nomic-embed-text` natively outputs 768-dimensional embeddings, making it a 1:1 match. The embedding service automatically normalizes any embedding vectors to match `VECTOR_DIMENSION`.

---

## Installation & Running

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Tests
```bash
python -m pytest -v
```

### 3. Start Local Development Server
```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
Interactive Swagger UI is available at: **`http://127.0.0.1:8000/docs`**

---

## Multi-Tenant Security & Scoping

Every request derives `company_id` from the caller's JWT:
- Checked claims: `company_id`, `app_metadata.company_id`, or `user_metadata.company_id`.
- Request body `company_id` is **never trusted** and automatically overwritten with the authenticated caller's company ID.

### ⚠️ Dev-Auth Escape Hatch (`X-Dev-Company-Id`)

For **local development only**, you can bypass JWT auth by sending the `X-Dev-Company-Id` header with any request. This is controlled by the `ALLOW_DEV_AUTH_HEADERS` environment variable:

| Setting | Behavior |
|---------|----------|
| `ALLOW_DEV_AUTH_HEADERS=true` | Accepts `X-Dev-Company-Id` header for company scoping (default in `.env.example`) |
| `ALLOW_DEV_AUTH_HEADERS=false` | Rejects the header; only signed JWTs are accepted |

> **🔒 IMPORTANT**: Set `ALLOW_DEV_AUTH_HEADERS=false` **before any non-local deployment** (staging, production, public-facing demo). Leaving it enabled allows any caller to impersonate any company by sending the header.

When `ALLOW_DEV_AUTH_HEADERS=true` and no JWT is provided, the header defaults to the Sable Farming Company ID (`ca6d3c2a-7e59-4e59-b6c6-42aa5acb3279`).

---

## Example `curl` Commands

### 1. Health Check
```bash
curl -X GET http://127.0.0.1:8000/health
```

### 2. Ingest Document (JSON)
```bash
curl -X POST http://127.0.0.1:8000/documents \
  -H "Content-Type: application/json" \
  -H "X-Dev-Company-Id: ca6d3c2a-7e59-4e59-b6c6-42aa5acb3279" \
  -d '{
    "title": "2026 Irrigation & Water Conservation SOP",
    "doc_type": "sop",
    "raw_text": "All tea and macadamia irrigation blocks must maintain strict soil moisture tracking. During peak dry season (September through November), borehole pumps may only operate between 05:00 and 11:00 to reduce transformer heat. Any emergency generator fuel allocations above 500 liters require executive confirmation."
  }'
```

### 3. Record Institutional Memory (Auto-embedded on write)
```bash
curl -X POST http://127.0.0.1:8000/memory \
  -H "Content-Type: application/json" \
  -H "X-Dev-Company-Id: ca6d3c2a-7e59-4e59-b6c6-42aa5acb3279" \
  -d '{
    "memory_type": "lesson",
    "summary": "Delayed macadamia nut harvesting caused significant moisture damage in Block C during late rains",
    "detail": "Quality downgraded by 15% due to delayed drying shed transit. In future seasons, harvest must conclude prior to October 25 regardless of crop moisture.",
    "importance": 5
  }'
```

### 4. Create a Goal
```bash
curl -X POST http://127.0.0.1:8000/goals \
  -H "Content-Type: application/json" \
  -H "X-Dev-Company-Id: ca6d3c2a-7e59-4e59-b6c6-42aa5acb3279" \
  -d '{
    "title": "Achieve 4,500 Metric Tons Macadamia Production",
    "metric_name": "macadamia_yield_tons",
    "target_value": 4500.0,
    "current_value": 1200.0,
    "unit": "tons",
    "status": "on_track",
    "starts_at": "2026-01-01",
    "due_at": "2026-12-31"
  }'
```

### 5. Chat with Executive COO Brain (`POST /coo/chat`)
```bash
curl -X POST http://127.0.0.1:8000/coo/chat \
  -H "Content-Type: application/json" \
  -H "X-Dev-Company-Id: ca6d3c2a-7e59-4e59-b6c6-42aa5acb3279" \
  -d '{
    "message": "What is our policy regarding borehole pumping during the dry season, and are there any past lessons about harvest timing?"
  }'
```

**Response includes citations**:
```json
{
  "conversation_id": "8f3b2024-5d57-4e45-9854-4a460ad77f8a",
  "message_id": "b304c4b9-8e42-4f27-9968-3ffdfd78ca28",
  "reply": "Based on [DOC-d249fd31-e129-47fe-bbd7-cb391e6b8296], borehole pumps must only run between 05:00 and 11:00 during peak dry season... Furthermore, according to past institutional experience [MEM-2c5dfc5e-2b5e-4c31-8977-832c32cf97b1], macadamia harvesting must finish before October 25 to avoid moisture penalties.",
  "cited_document_ids": ["d249fd31-e129-47fe-bbd7-cb391e6b8296"],
  "cited_memory_ids": ["2c5dfc5e-2b5e-4c31-8977-832c32cf97b1"],
  "retrieved_documents_count": 1,
  "retrieved_memories_count": 1
}
```
