import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datasets import load_dataset
from core.embeddings.sparse import BM25SparseEncoder
from core.config import settings
from core import get_logger

logger = get_logger("fit_bm25_encoder")


def fit_bm25_on_dataset(
    dataset_name: str,
    text_column: str,
    split: str = "train",
    limit: int | None = None,
    output_path: str | None = None,
):
    """
    Streams a HF dataset's text column once to fit BM25 term statistics (document
    frequency, average doc length) on the real corpus, then persists the params so
    ingestion and querying use consistent sparse-vector weighting.

    Run this once before (re-)ingesting -- BM25 params must be fit before the sparse
    vectors used by the vector index are generated.
    """
    output_path = output_path or settings.BM25_PARAMS_PATH
    logger.info(f"Loading dataset '{dataset_name}' (Split: {split}) to fit BM25...")

    dataset = load_dataset(dataset_name, split=split, streaming=True)

    corpus = []
    for i, row in enumerate(dataset):
        if limit and i >= limit:
            break
        text = row.get(text_column)
        if text:
            corpus.append(text)

    logger.info(f"Fitting BM25 on {len(corpus)} documents...")
    encoder = BM25SparseEncoder.fit(corpus)
    encoder.save(output_path)
    logger.info(f"Saved fitted BM25 params to {output_path}")


if __name__ == "__main__":
    fit_bm25_on_dataset(
        dataset_name="neural-bridge/rag-dataset-12000",
        text_column="context",
        split="train",
    )
