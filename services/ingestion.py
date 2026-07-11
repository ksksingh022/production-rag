import hashlib
from langchain_text_splitters import RecursiveCharacterTextSplitter
from core.embeddings import hf_embedding_client  # Dynamic Strategy Engine Pattern Integrated
from core.embeddings.sparse import BM25SparseEncoder
from core.config import settings
from core import vector_manager, cache_manager, get_logger
from services.cache_service import CACHE_EPOCH_KEY

logger = get_logger("ingestion_service")

# Bumping this forces every doc's hash to change, so previously-ingested vectors get
# re-embedded (with sparse_values / new chunk boundaries) instead of being skipped by the hash check.
INGEST_SCHEMA_VERSION = "v3_token_based_chunking"

class IngestionService:
    def __init__(self):
        self.vector_index = vector_manager.get_index()
        self.valkey_client = cache_manager.get_client()
        self.text_splitter = self._build_text_splitter()
        self.sparse_encoder = BM25SparseEncoder.load_or_default(settings.BM25_PARAMS_PATH)

    def _build_text_splitter(self) -> RecursiveCharacterTextSplitter:
        """Token-aware splitter, sized against the embedding model's own tokenizer so
        chunks never silently get truncated at the model's max sequence length."""
        chunk_size = settings.CHUNK_SIZE_TOKENS
        model_max_tokens = hf_embedding_client.max_tokens

        if model_max_tokens and chunk_size > model_max_tokens:
            logger.warning(
                f"CHUNK_SIZE_TOKENS ({chunk_size}) exceeds the embedding model's max "
                f"sequence length ({model_max_tokens}). Capping to {model_max_tokens} "
                f"to avoid silent truncation during embedding."
            )
            chunk_size = model_max_tokens

        tokenizer = hf_embedding_client.get_tokenizer()
        if tokenizer:
            return RecursiveCharacterTextSplitter.from_huggingface_tokenizer(
                tokenizer=tokenizer,
                chunk_size=chunk_size,
                chunk_overlap=settings.CHUNK_OVERLAP_TOKENS,
            )

        # Fallback for providers without a tokenizer (e.g. Ollama): approximate tokens as ~4 chars/token
        logger.warning("Embedding provider has no tokenizer; falling back to approximate char-based sizing.")
        return RecursiveCharacterTextSplitter(
            chunk_size=chunk_size * 4,
            chunk_overlap=settings.CHUNK_OVERLAP_TOKENS * 4,
        )

    def _calculate_hash(self, text: str) -> str:
        """Text ka unique MD5 hash nikalta hai, schema version ke saath (format change pe re-ingest trigger)."""
        return hashlib.md5(f"{INGEST_SCHEMA_VERSION}:{text}".encode("utf-8")).hexdigest()

    def ingest_raw_text(self, document_id: str, raw_text: str, metadata: dict = None) -> str:
        """
        Sync function jo background worker thread mein chalegi. 
        Saves process tracking flags inside Valkey & pushes to Pinecone.
        """
        if not metadata:
            metadata = {}

        status_key = f"status:{document_id}"
        redis_hash_key = f"doc_hash:{document_id}"

        # 1. LIVE MONITORING: Worker state instantly 'processing' mark karo
        self.valkey_client.set(status_key, "processing")

        current_hash = self._calculate_hash(raw_text)
        existing_hash = self.valkey_client.get(redis_hash_key)

        # 2. INCREMENTAL INGESTION CHECK
        if existing_hash == current_hash:
            logger.info(f"Document {document_id} has not changed. Skipping ingestion (Incremental Support).")
            self.valkey_client.set(status_key, "skipped")
            return "skipped_no_change"

        logger.info(f"Starting async ingestion pipeline for document: {document_id}")
        try:
            chunks = self.text_splitter.split_text(raw_text)
            vectors_to_upsert = []
            
            # Deterministic IDs array for perfect target cleanup on Pinecone Serverless
            chunk_ids_to_clean = [f"{document_id}#chunk_{i}" for i in range(len(chunks))]

            # 3. CLEAN UP (RE-INDEXING FIX)
            # Agar file pehle ingest ho chuki thi aur ab change hui h, toh update krne se pehle explicitly clear targets
            if existing_hash:
                logger.info(f"Document {document_id} content modified. Cleaning old vector states safely...")
                try:
                    # Explicit array optimization to handle serverless constraint without wildcards
                    self.vector_index.delete(ids=chunk_ids_to_clean, namespace="rag-documents")
                except Exception as clean_err:
                    logger.warning(f"Metadata clean bypass or non-existent prior ids: {str(clean_err)}")

            # 4. CHUNKING & EMBEDDINGS (BATCHED) -- DENSE + SPARSE FOR HYBRID SEARCH
            # REWRITTEN: Ab koi OpenAI direct coupling nahi, dynamic backend wrapper strategy active hai
            # Batch calls instead of one-embedding-per-chunk loop -- much faster for multi-chunk docs
            chunk_dense_embeddings = hf_embedding_client.get_embeddings(chunks)
            chunk_sparse_embeddings = self.sparse_encoder.encode_documents(chunks)

            for i, (chunk_text, dense_embedding, sparse_embedding) in enumerate(
                zip(chunks, chunk_dense_embeddings, chunk_sparse_embeddings)
            ):
                chunk_id = chunk_ids_to_clean[i]

                payload_metadata = {
                    **metadata,
                    "text": chunk_text,
                    "chunk_index": i,
                    "doc_hash": current_hash
                }
                vectors_to_upsert.append({
                    "id": chunk_id,
                    "values": dense_embedding,
                    "sparse_values": sparse_embedding,
                    "metadata": payload_metadata
                })

            # 5. PINECONE BATCH UPSERT
            batch_size = 100
            for i in range(0, len(vectors_to_upsert), batch_size):
                batch = vectors_to_upsert[i : i + batch_size]
                self.vector_index.upsert(vectors=batch, namespace="rag-documents")
            
            # 6. TRANSACTION SUCCESS PERSISTENCE
            self.valkey_client.set(redis_hash_key, current_hash)
            self.valkey_client.set(status_key, "completed")

            # Bump the query-cache epoch so previously-cached answers (now potentially
            # stale against this updated/new content) age out instead of being served.
            self.valkey_client.incr(CACHE_EPOCH_KEY)

            logger.info(f"Successfully ingested {len(vectors_to_upsert)} chunks for document {document_id}")
            return "success"

        except Exception as e:
            # 7. EXCEPTION TRACKING STATE
            self.valkey_client.set(status_key, "failed")
            logger.error(f"Ingestion pipeline crashed for document {document_id}: {str(e)}")
            return "failed"

# Global clean service handler
ingestion_service = IngestionService()