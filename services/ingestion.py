import hashlib
from langchain_text_splitters import RecursiveCharacterTextSplitter
from core.embeddings import hf_embedding_client  # Dynamic Strategy Engine Pattern Integrated
from core import vector_manager, cache_manager, get_logger

logger = get_logger("ingestion_service")

class IngestionService:
    def __init__(self):
        self.vector_index = vector_manager.get_index()
        self.valkey_client = cache_manager.get_client()
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)

    def _calculate_hash(self, text: str) -> str:
        """Text ka unique MD5 hash nikalta hai."""
        return hashlib.md5(text.encode("utf-8")).hexdigest()

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

            # 4. CHUNKING & EMBEDDINGS LOOP
            for i, chunk_text in enumerate(chunks):
                chunk_id = chunk_ids_to_clean[i]
                
                # REWRITTEN: Ab koi OpenAI direct coupling nahi, dynamic backend wrapper strategy active hai
                embedding = hf_embedding_client.get_embedding(chunk_text)
                
                payload_metadata = {
                    **metadata,
                    "text": chunk_text,
                    "chunk_index": i,
                    "doc_hash": current_hash
                }
                vectors_to_upsert.append((chunk_id, embedding, payload_metadata))

            # 5. PINECONE BATCH UPSERT
            batch_size = 100
            for i in range(0, len(vectors_to_upsert), batch_size):
                batch = vectors_to_upsert[i : i + batch_size]
                self.vector_index.upsert(vectors=batch, namespace="rag-documents")
            
            # 6. TRANSACTION SUCCESS PERSISTENCE
            self.valkey_client.set(redis_hash_key, current_hash)
            self.valkey_client.set(status_key, "completed")
            
            logger.info(f"Successfully ingested {len(vectors_to_upsert)} chunks for document {document_id}")
            return "success"

        except Exception as e:
            # 7. EXCEPTION TRACKING STATE
            self.valkey_client.set(status_key, "failed")
            logger.error(f"Ingestion pipeline crashed for document {document_id}: {str(e)}")
            return "failed"

# Global clean service handler
ingestion_service = IngestionService()