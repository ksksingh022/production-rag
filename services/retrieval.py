from dataclasses import dataclass
from core.embeddings import hf_embedding_client
from core.embeddings.sparse import BM25SparseEncoder
from core.config import settings
from core import vector_manager, get_logger

logger = get_logger("retrieval_service")


@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    score: float
    metadata: dict


def _hybrid_scale(dense: list[float], sparse: dict, alpha: float) -> tuple[list[float], dict]:
    """Pinecone's recommended convex combination for sparse-dense hybrid search:
    scale dense by alpha and sparse by (1-alpha) before querying a dotproduct index.
    alpha=1 -> pure semantic/dense, alpha=0 -> pure keyword/sparse."""
    if not 0 <= alpha <= 1:
        raise ValueError("alpha must be between 0 and 1")
    scaled_dense = [v * alpha for v in dense]
    scaled_sparse = {
        "indices": sparse["indices"],
        "values": [v * (1 - alpha) for v in sparse["values"]],
    }
    return scaled_dense, scaled_sparse


class RetrievalService:
    """Hybrid (dense + sparse/BM25) retrieval over the Pinecone index populated by
    services/ingestion.py. Requires the index to use the dotproduct metric."""

    def __init__(self):
        self.vector_index = vector_manager.get_index()
        self.sparse_encoder = BM25SparseEncoder.load_or_default(settings.BM25_PARAMS_PATH)

    def retrieve(
        self,
        query: str,
        top_n: int | None = None,
        alpha: float | None = None,
        filters: dict | None = None,
    ) -> list[RetrievedChunk]:
        """Returns up to top_n candidate chunks ranked by hybrid score, highest first."""
        top_n = top_n or settings.RETRIEVE_N
        alpha = settings.HYBRID_ALPHA if alpha is None else alpha

        dense_vector = hf_embedding_client.get_embedding(query)
        sparse_vector = self.sparse_encoder.encode_query(query)
        scaled_dense, scaled_sparse = _hybrid_scale(dense_vector, sparse_vector, alpha)

        result = self.vector_index.query(
            vector=scaled_dense,
            sparse_vector=scaled_sparse,
            top_k=top_n,
            namespace=settings.PINECONE_NAMESPACE,
            include_metadata=True,
            filter=filters,
        )

        candidates = []
        for match in result.get("matches", []):
            metadata = match.get("metadata", {}) or {}
            candidates.append(
                RetrievedChunk(
                    chunk_id=match["id"],
                    text=metadata.get("text", ""),
                    score=match["score"],
                    metadata=metadata,
                )
            )

        logger.info(f"Retrieved {len(candidates)} candidates for query (alpha={alpha}, top_n={top_n})")
        return candidates

    def fetch_chunks(self, chunk_ids: list[str], scores_by_id: dict[str, float] | None = None) -> list[RetrievedChunk]:
        """Reconstructs chunks by id (e.g. to replay a historical answer's sources without
        re-running retrieval). scores_by_id lets the caller reattach previously-computed
        scores, since a plain Pinecone fetch doesn't return a similarity score."""
        if not chunk_ids:
            return []
        scores_by_id = scores_by_id or {}

        result = self.vector_index.fetch(ids=chunk_ids, namespace=settings.PINECONE_NAMESPACE)
        vectors = result.get("vectors", {})

        chunks = []
        for chunk_id in chunk_ids:
            vector = vectors.get(chunk_id)
            if not vector:
                continue
            metadata = vector.get("metadata", {}) or {}
            chunks.append(
                RetrievedChunk(
                    chunk_id=chunk_id,
                    text=metadata.get("text", ""),
                    score=scores_by_id.get(chunk_id, 0.0),
                    metadata=metadata,
                )
            )
        return chunks


retrieval_service = RetrievalService()
