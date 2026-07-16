# BridgeMind

A production-grade Retrieval-Augmented Generation (RAG) system: ingest documents, index
them with hybrid (dense + sparse) search, and answer natural-language questions with
grounded, cited responses — with caching, reranking, multi-provider LLM support,
observability, and a full web UI on top.

Built and iterated end-to-end with [Claude Code](https://claude.com/claude-code).

---

## What this is

BridgeMind takes raw text documents, chunks and embeds them into a vector index, and
serves a `query` API that retrieves the most relevant chunks for a question, reranks
them, and asks an LLM to answer **using only that retrieved context** — the core RAG
pattern, built out with the pieces a real deployment actually needs:

- **Hybrid retrieval** (dense semantic + BM25 keyword search fused in one query) instead
  of dense-only, so exact-keyword and paraphrased questions both work.
- **Cross-encoder reranking** on top of the initial retrieval for better relevance.
- **Multi-provider, multi-model generation** — OpenAI, OpenRouter (100+ models via one
  integration, including free-tier models), or a local OpenAI-compatible server — chosen
  per-request, never hardcoded.
- **Query caching** in Valkey (Redis-compatible), with cache invalidation tied to
  re-ingestion so stale answers don't linger.
- **Full observability** — Prometheus metrics, structured request logs, and every query
  persisted to Postgres for analytics (latency percentiles, cache-hit rate, token/cost
  tracking, top queries).
- **A real UI** — not just a Swagger page: a React app with a streaming chat-style Ask
  view, a query history sidebar, and an analytics dashboard with live charts.

The current corpus loaded for testing is
[`neural-bridge/rag-dataset-12000`](https://huggingface.co/datasets/neural-bridge/rag-dataset-12000)
from Hugging Face — a general-purpose, diverse-topic dataset (tech, finance, health,
sports, science, etc.), used here as a stand-in for whatever real corpus this gets
pointed at.

---

## Architecture

```mermaid
flowchart TB
    UI["React + Vite UI\nAsk - History - Dashboard"] -->|"HTTPS / SSE"| MW["FastAPI middleware\nCORS, rate limit, API key, request-ID"]

    subgraph routes["API routes"]
        direction LR
        QR["/query\n/query/stream"]
        HR["/history"]
        SR["/stats\n/stats/timeline"]
        FR["/feedback"]
    end
    MW --> routes

    QR --> CACHE{"cache\nhit?"}
    CACHE -->|yes| QCACHE
    CACHE -->|no| RET["RetrievalService\nhybrid dense+sparse search"]
    RET --> RANK["Cross-encoder\nreranker"]
    RANK --> GEN["GenerationService\nguard-output detection + retry"]

    subgraph llm["LLM layer"]
        direction LR
        FACTORY["LLMFactory"] --> OR["OpenRouter"] & OAI["OpenAI"] & LOCAL["Local"]
    end
    GEN --> FACTORY

    GEN --> QCACHE[("Valkey\nquery cache")]
    GEN --> PG[("Postgres\nquery_logs, feedback")]
    RET --> PC[("Pinecone\ndotproduct index")]
    HR --> PG
    HR --> PC
    SR --> PG
    FR --> PG

    subgraph ingest["Ingestion (offline batch script)"]
        direction LR
        HFD["HF dataset"] --> CHUNK["Token-aware\nchunking"] --> ENC["Dense + sparse\nencoding"] --> UPSERT["Upsert"]
    end
    UPSERT --> PC
    UPSERT --> DOCCACHE[("Valkey\ndoc-hash + checkpoint")]

    style PC fill:#eef4fc,stroke:#2a78d6
    style QCACHE fill:#eef4fc,stroke:#2a78d6
    style DOCCACHE fill:#eef4fc,stroke:#2a78d6
    style PG fill:#eef4fc,stroke:#2a78d6
```

**Request lifecycle for `POST /api/v1/query`:** normalize + hash the query → check the
Valkey cache → on a miss, embed the query (dense + sparse), run a hybrid Pinecone search,
rerank the top candidates with a cross-encoder, build a grounded prompt, generate an
answer (with automatic retry if the model returns a non-answer), estimate cost from real
token usage, persist the full result to Postgres, write through to the cache, and return
the answer with sources and per-stage timing metrics. The streaming variant
(`/api/v1/query/stream`) does the same but streams generation tokens over SSE, buffering
just enough of the start of the stream to catch and retry a bad response before any of it
reaches the client.

---

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| API framework | FastAPI + Uvicorn | async, typed, auto-generated OpenAPI docs |
| Vector store | Pinecone (serverless, `dotproduct` metric) | native sparse+dense hybrid search |
| Dense embeddings | `sentence-transformers` (`all-MiniLM-L6-v2`) | local, no per-call API cost |
| Sparse embeddings | BM25 via `pinecone-text`, fit on the ingested corpus | lexical/keyword matching |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` | joint query-chunk attention, better than raw vector distance |
| LLM access | `openai` SDK against OpenAI, OpenRouter, or any OpenAI-compatible local server | one client, swappable `base_url`/`api_key`, model chosen per-request |
| Cache | Valkey (Redis-compatible) | query cache, ingestion checkpoints, doc-hash tracking for incremental ingestion |
| Relational store | Postgres (SQLAlchemy) | query logs, feedback, analytics |
| Metrics | `prometheus-fastapi-instrumentator` + custom counters/histograms | `/metrics` scrape endpoint |
| Rate limiting | `slowapi` | per-key/IP request limits |
| Frontend | React 19 + TypeScript + Vite | Ask view (SSE streaming), history sidebar, analytics dashboard with hand-rolled SVG charts |

---

## Project structure

```
core/               Shared infra: config, DB, cache, vector store, embeddings, LLM
                     factory, reranker, Prometheus metrics
  embeddings/        Dense (sentence-transformers) + sparse (BM25) encoders
  llm/               Provider-agnostic LLM layer: base interface, OpenAI-compatible
                     client, factory, model registry (cost/context per model)
services/           Business logic
  ingestion.py       Chunk -> embed (dense+sparse) -> upsert to Pinecone
  retrieval.py       Hybrid search + fetch-by-id (for replaying history)
  generation.py      Prompt construction, guard-output detection + retry, streaming
  query.py           Orchestrates cache -> retrieve -> rerank -> generate -> log -> cache
  cache_service.py   Query cache (Valkey), epoch-based invalidation on re-ingest
  analytics.py       Query logging, stats aggregation, timeline, feedback
api/
  routes/            /query, /query/stream, /feedback, /history, /stats, /health
  schemas.py         Pydantic request/response models
  middleware.py       Request-ID tagging, structured logging, error handling
  dependencies.py     API-key auth
  rate_limit.py       slowapi rate limiter
models/             SQLAlchemy models: QueryLog, Feedback
scripts/
  import_hf_datasets.py   Ingest a Hugging Face dataset (batched, checkpointed, resumable)
  fit_bm25_encoder.py     Fit BM25 term statistics on the corpus before ingesting
ui/                 React + Vite frontend
  src/context/            Shared Ask-view state (query, streaming, history load)
  src/components/         AskView, Sidebar (history), Dashboard, charts/
  src/lib/                Typed API client, SSE stream parser
main.py             FastAPI app assembly (middleware, routers, Prometheus)
```

---

## Getting started

### Prerequisites

- Python 3.12+, Node 20+
- A Pinecone index created with the **`dotproduct`** metric (required for hybrid search)
- A Postgres database and a Valkey/Redis instance
- An OpenRouter API key (or OpenAI/local — see `core/config.py`)

### Backend

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

Create `.env` in the project root:

```bash
DATABASE_URL=postgresql://user:pass@host:5432/dbname
VALKEY_URL=rediss://user:pass@host:port
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=...
PINECONE_HOSTNAME=...
OPENROUTER_API_KEY=...
```

Ingest a corpus (fits BM25 on the corpus first, then chunks/embeds/upserts to Pinecone,
checkpointed so it can resume if interrupted):

```bash
python3 scripts/fit_bm25_encoder.py
python3 scripts/import_hf_datasets.py
```

Run the API:

```bash
uvicorn main:app --reload
```

### Frontend

```bash
cd ui
cp .env.example .env   # set VITE_API_BASE_URL to the backend above
npm install
npm run dev
```

Open `http://localhost:5173` — the **Ask** tab for querying, the **Dashboard** tab for
live analytics.

---

## API reference

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/query` | Ask a question, get a JSON answer + sources + metrics |
| `POST` | `/api/v1/query/stream` | Same, streamed via SSE |
| `POST` | `/api/v1/feedback` | 👍/👎 a previous answer (one vote per query, enforced server-side) |
| `GET` | `/api/v1/history` | Recent queries with sources reconstructed for replay |
| `GET` | `/api/v1/stats` | Aggregate dashboard stats |
| `GET` | `/api/v1/stats/timeline` | Per-query timeline for charts |
| `GET` | `/health/live` / `/health/ready` | Liveness / readiness (checks Pinecone, Valkey, Postgres) |
| `GET` | `/metrics` | Prometheus scrape endpoint |

Full interactive docs at `/docs` once the server is running.

---

## Notable design decisions

- **Never hardcode a model.** Provider and model are resolved per-request with a config
  default, backed by a small registry of context-window/cost data — swapping models is a
  config change, not a code change.
- **Guard-model detection.** OpenRouter's free-tier router occasionally selects a
  content-moderation model instead of a chat model, which returns a safety
  classification (e.g. `"User Safety: safe"`) instead of an answer. `services/generation.py`
  detects this shape and automatically retries rather than surfacing it as a real answer.
- **Token-aware chunking.** Chunks are sized against the embedding model's actual
  tokenizer and max sequence length, not a character count — avoids silent truncation.
- **Cache correctness over convenience.** A cache hit is logged as its own entry with
  its own near-zero latency and `$0` cost, rather than replaying the original
  generation's numbers — so dashboard aggregates (total tokens, cost, cache-hit rate)
  stay honest instead of double-counting.
- **Incremental, resumable ingestion.** Document hashes and stream checkpoints live in
  Valkey, so re-running the ingestion script skips unchanged documents and resumes from
  where it left off after an interruption.

## Known limitations / not yet built

- Migrations run via `Base.metadata.create_all` — no Alembic migration history yet.
- No containerization (Dockerfile/compose) or CI pipeline yet.
- No automated retrieval/answer quality evaluation harness.
- Semantic (similarity-based) query caching and OpenTelemetry tracing are not implemented,
  only exact-match caching and Prometheus metrics.
