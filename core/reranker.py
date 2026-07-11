from sentence_transformers import CrossEncoder
from core.config import settings
from core.logger import get_logger

logger = get_logger("reranker")


class CrossEncoderReranker:
    """Rescores retrieval candidates with a cross-encoder, which jointly attends over
    (query, chunk) pairs instead of comparing independent embeddings -- meaningfully
    more accurate than vector distance alone, at the cost of one forward pass per pair."""

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.RERANK_MODEL
        self.model = CrossEncoder(self.model_name)

    def rerank(self, query: str, candidates: list, top_k: int) -> list:
        """candidates: list of objects with a `.text` attribute (e.g. RetrievedChunk).
        Returns the top_k candidates re-scored and sorted by cross-encoder relevance,
        with each candidate's `.score` overwritten by the rerank score."""
        if not candidates:
            return []

        pairs = [(query, c.text) for c in candidates]
        scores = self.model.predict(pairs)

        rescored = list(zip(candidates, scores))
        rescored.sort(key=lambda pair: pair[1], reverse=True)

        top = rescored[:top_k]
        for candidate, score in top:
            candidate.score = float(score)

        return [candidate for candidate, _ in top]


reranker = CrossEncoderReranker()
