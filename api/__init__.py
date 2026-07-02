# my_rag_app/
# ├── .github/workflows/      # CI/CD pipelines
# ├── api/                    # FastAPI or routing logic (e.g., /query, /ingest)
# ├── core/                   # Global configs and logging utilities
# ├── database/               # Database connection logic (Postgres, Redis)
# ├── ingestion/              # Document loading, parsing, and chunking
# ├── embeddings/             # Text embedding generation models
# ├── vectorstore/            # Vector DB setup (e.g., Pinecone, Chroma, Qdrant)
# ├── retrieval/              # Retriever algorithms, reranking, and search
# ├── generation/             # Prompt engineering and LLM invocation logic
# ├── tests/                  # Unit and integration tests
# ├── .env                    # Environment variables (API keys, DB URLs)
# └── main.py                 # Application entry point
