import os
from pinecone_text.sparse import BM25Encoder
from core.logger import get_logger

logger = get_logger("sparse_encoder")


class BM25SparseEncoder:
    """Wraps pinecone-text's BM25Encoder for lexical (sparse) vectors used in hybrid search."""

    def __init__(self, encoder: BM25Encoder):
        self._encoder = encoder

    @classmethod
    def fit(cls, corpus: list[str]) -> "BM25SparseEncoder":
        """Fits BM25 term statistics on the given corpus texts."""
        encoder = BM25Encoder()
        encoder.fit(corpus)
        return cls(encoder)

    @classmethod
    def load(cls, path: str) -> "BM25SparseEncoder":
        """Loads previously fitted BM25 params from disk."""
        encoder = BM25Encoder().load(path)
        return cls(encoder)

    @classmethod
    def load_or_default(cls, path: str) -> "BM25SparseEncoder":
        """Loads fitted params if present, otherwise falls back to pinecone-text's
        generic pre-fit (MS MARCO) params. The default is a reasonable stand-in but
        should be replaced by running scripts/fit_bm25_encoder.py on your own corpus
        for better lexical relevance."""
        if os.path.exists(path):
            logger.info(f"Loading fitted BM25 params from {path}")
            return cls.load(path)
        logger.warning(
            f"No fitted BM25 params found at {path}. Falling back to pinecone-text's "
            f"generic default encoder. Run scripts/fit_bm25_encoder.py to fit on your own corpus."
        )
        return cls(BM25Encoder().default())

    def save(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._encoder.dump(path)

    def encode_documents(self, texts: list[str]) -> list[dict]:
        """Returns a list of sparse vectors ({'indices': [...], 'values': [...]}), one per text."""
        if not texts:
            return []
        result = self._encoder.encode_documents(texts)
        return result if isinstance(result, list) else [result]

    def encode_query(self, text: str) -> dict:
        """Returns a single sparse vector for a query string."""
        return self._encoder.encode_queries(text)
