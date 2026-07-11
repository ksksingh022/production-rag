import sys
import os
import json
import time

# Taaki Python core aur services folder ko sahi se detect kar sake
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datasets import load_dataset
from services.ingestion import ingestion_service, INGEST_SCHEMA_VERSION
from core import get_logger, cache_manager

logger = get_logger("hf_import_script")


def _checkpoint_key(dataset_name: str, split: str) -> str:
    # Schema version is baked into the key so an ingestion-format change (new chunking,
    # hybrid vectors, etc.) automatically starts a fresh checkpoint instead of resuming
    # -- or short-circuiting as "completed" -- against an incompatible old run.
    return f"hf_import:checkpoint:{INGEST_SCHEMA_VERSION}:{dataset_name}:{split}"


def _load_checkpoint(valkey_client, dataset_name: str, split: str) -> dict:
    raw = valkey_client.get(_checkpoint_key(dataset_name, split))
    if not raw:
        return {"consumed": 0, "processed": 0, "failed": 0, "status": "not_started"}
    return json.loads(raw)


def _save_checkpoint(valkey_client, dataset_name: str, split: str, checkpoint: dict):
    valkey_client.set(_checkpoint_key(dataset_name, split), json.dumps(checkpoint))


def import_and_embed_hf_dataset(
    dataset_name: str,
    text_column: str,
    id_column: str,
    provider: str = "openai",
    model_name: str | None = None,
    split: str = "train",
    limit: int = 100,
    batch_size: int = 50,
    resume: bool = True,
):
    """
    Hugging Face dataset ko load karke loop mein batch ingest karta hai.
    Har batch ke baad Valkey mein checkpoint save hota hai, taaki interruption
    ke baad wahi se resume ho sake instead of restarting from row 0.
    """
    valkey_client = cache_manager.get_client()
    checkpoint = _load_checkpoint(valkey_client, dataset_name, split) if resume else {
        "consumed": 0, "processed": 0, "failed": 0, "status": "not_started"
    }

    if checkpoint["status"] == "completed" and resume:
        logger.info(f"Dataset '{dataset_name}' [{split}] already marked completed. Pass resume=False to re-run.")
        return

    start_consumed = checkpoint["consumed"]
    processed = checkpoint["processed"]
    failed = checkpoint["failed"]

    logger.info(f"Loading dataset '{dataset_name}' (Split: {split}) from Hugging Face...")
    if start_consumed:
        logger.info(f"Resuming from checkpoint: {start_consumed} rows already consumed, {processed} previously ingested.")

    try:
        # streaming=True se data poora RAM mein download nahi hota, ek-ek karke stream hota h (Best for large datasets)
        dataset = load_dataset(dataset_name, split=split, streaming=True)
        if start_consumed:
            dataset = dataset.skip(start_consumed)

        logger.info(f"Starting ingestion using provider: '{provider}'... target={limit} rows, batch_size={batch_size}")

        consumed_this_run = 0
        batch_start_time = time.time()
        run_start_time = batch_start_time
        hit_limit = False

        for row in dataset:
            if processed >= limit:
                hit_limit = True
                break

            consumed_this_run += 1
            raw_text = row.get(text_column)
            # Agar primary ID column na ho to loop index ko ID bana denge
            doc_id = str(row.get(id_column, f"hf_{dataset_name.replace('/', '_')}_{start_consumed + consumed_this_run}"))

            if not raw_text:
                continue

            # Extra metadata jo aap index mein save rakhna chahte ho
            metadata = {
                "source": "huggingface",
                "dataset_name": dataset_name
            }

            status = ingestion_service.ingest_raw_text(
                document_id=doc_id,
                raw_text=raw_text,
                metadata=metadata
            )

            if status == "success":
                processed += 1
            elif status == "skipped_no_change":
                logger.info(f"Record {doc_id} skipped (already exists with same hash).")
                processed += 1
            else:
                failed += 1
                logger.warning(f"Record {doc_id} failed to ingest (status={status}).")

            # --- CHECKPOINT + PROGRESS LOGGING AT BATCH BOUNDARY ---
            if consumed_this_run % batch_size == 0 or processed >= limit:
                checkpoint = {
                    "consumed": start_consumed + consumed_this_run,
                    "processed": processed,
                    "failed": failed,
                    "status": "in_progress",
                }
                _save_checkpoint(valkey_client, dataset_name, split, checkpoint)

                elapsed = time.time() - run_start_time
                batch_elapsed = time.time() - batch_start_time
                rate = processed / elapsed if elapsed > 0 else 0
                remaining = max(limit - processed, 0)
                eta_seconds = remaining / rate if rate > 0 else float("inf")
                pct = (processed / limit * 100) if limit else 0

                logger.info(
                    f"[PROGRESS] {processed}/{limit} rows ({pct:.1f}%) | failed={failed} | "
                    f"batch took {batch_elapsed:.1f}s | rate={rate:.2f} rows/s | ETA={eta_seconds/60:.1f} min"
                )
                batch_start_time = time.time()

        # The for-loop only exits via the limit break above or by the stream running out
        # of rows -- either way there's nothing left to do this run, so it's "completed".
        # (Only an exception, handled below, leaves the checkpoint at "in_progress".)
        final_status = "completed"
        checkpoint = {
            "consumed": start_consumed + consumed_this_run,
            "processed": processed,
            "failed": failed,
            "status": final_status,
        }
        _save_checkpoint(valkey_client, dataset_name, split, checkpoint)

        total_elapsed = time.time() - run_start_time
        reason = "target limit reached" if hit_limit else "dataset stream exhausted (fewer rows than limit)"
        logger.info(
            f"Mubarak ho! Finished run: processed={processed}/{limit}, failed={failed}, "
            f"status={final_status} ({reason}), total_time={total_elapsed/60:.1f} min."
        )

    except Exception as e:
        # Interruption ya crash ho, checkpoint already batch-boundary par saved hai -- rerun same call se resume hoga
        logger.critical(f"Script failed/interrupted: {str(e)}. Progress up to last checkpoint has been saved.")
        raise


if __name__ == "__main__":
    # Dataset: 'neural-bridge/rag-dataset-12000' -- despite the name, the 'train' split
    # has 9,600 rows (the other 2,400 are in 'test'). limit is set to 9600 accordingly;
    # if limit is set higher than the split actually has, the stream just exhausts early
    # and the run still correctly marks itself "completed" (fixed above).
    # text_column: 'context', id_column: 'id'
    # resume=True (default) -> agar pehle se checkpoint mila to wahi se continue karega

    import_and_embed_hf_dataset(
        dataset_name="neural-bridge/rag-dataset-12000",
        text_column="context",
        id_column="id",
        provider="huggingface",             # Yahan aap 'openai' bhi likh sakte ho
        model_name="all-MiniLM-L6-v2",     # Model selection dynamic runtime par
        limit=9600,
        batch_size=50,
        resume=True,
    )
