import sys
import os

# Taaki Python core aur services folder ko sahi se detect kar sake
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datasets import load_dataset
from services.ingestion import ingestion_service
from core import get_logger

logger = get_logger("hf_import_script")

def import_and_embed_hf_dataset(
    dataset_name: str, 
    text_column: str, 
    id_column: str,
    provider: str = "openai",
    model_name: str | None = None,
    split: str = "train", 
    limit: int = 100
):
    """
    Hugging Face dataset ko load karke loop mein batch ingest karta hai.
    """
    logger.info(f"Loading dataset '{dataset_name}' (Split: {split}) from Hugging Face...")
    
    try:
        # streaming=True se data poora RAM mein download nahi hota, ek-ek karke stream hota h (Best for large datasets)
        dataset = load_dataset(dataset_name, split=split, streaming=True)
        
        count = 0
        logger.info(f"Starting ingestion using provider: '{provider}'...")

        for row in dataset:
            if count >= limit:
                break
                
            raw_text = row.get(text_column)
            # Agar primary ID column na ho to loop index ko ID bana denge
            doc_id = str(row.get(id_column, f"hf_{dataset_name.replace('/', '_')}_{count}"))
            
            if not raw_text:
                continue

            # Extra metadata jo aap index mein save rakhna chahte ho
            metadata = {
                "source": "huggingface",
                "dataset_name": dataset_name
            }

            logger.info(f"Ingesting record {count+1}/{limit} (ID: {doc_id})")
            
            # --- HAMARI SMART SERVICE CALL HUI ---
            status = ingestion_service.ingest_raw_text(
                document_id=doc_id,
                raw_text=raw_text,
                metadata=metadata
            )
            
            if status == "success":
                count += 1
            elif status == "skipped_no_change":
                logger.info(f"Record {doc_id} skipped (already exists with same hash).")
                count += 1 # Count as processed
                
        logger.info(f"Mubarak ho! Successfully processed {count} rows from Hugging Face.")

    except Exception as e:
        logger.critical(f"Script failed: {str(e)}")

if __name__ == "__main__":
    # Example Setup: Using a standard tiny QA dataset
    # Dataset: 'squad' (Stanford Question Answering Dataset)
    # text_column: 'context' (Bada para jisme se answers milte hain)
    # id_column: 'id'
    
    import_and_embed_hf_dataset(
        dataset_name="neural-bridge/rag-dataset-12000",
        text_column="context",
        id_column="id",
        provider="huggingface",             # Yahan aap 'openai' bhi likh sakte ho
        model_name="all-MiniLM-L6-v2",     # Model selection dynamic runtime par
        limit=10                             # Testing ke liye pehle sirf 10 rows daal kar dekhein
    )