"""
Pre-download Hugging Face models to be baked into the Docker image.
Saves models to local directories for offline use.
"""
import os
import logging
from sentence_transformers import SentenceTransformer, CrossEncoder
from pathlib import Path
import sys

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def download_models():
    # Base dir for models inside the container
    base_model_dir = Path("/app/models")
    if not base_model_dir.exists():
        base_model_dir = Path("./models") # Fallback for local testing
    
    emb_path = base_model_dir / "embeddings"
    reranker_path = base_model_dir / "reranker"
    
    emb_path.mkdir(parents=True, exist_ok=True)
    reranker_path.mkdir(parents=True, exist_ok=True)

    # 1. Embedding Model
    emb_model_name = settings.EMBEDDING_MODEL
    logger.info(f"Downloading & saving embedding model '{emb_model_name}' to {emb_path}...")
    model = SentenceTransformer(emb_model_name)
    model.save(str(emb_path))
    
    # 2. Reranker Model
    reranker_model_name = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    logger.info(f"Downloading & saving reranker model '{reranker_model_name}' to {reranker_path}...")
    reranker = CrossEncoder(reranker_model_name)
    reranker.save(str(reranker_path))
    
    logger.info("✅ All models baked into local directories successfully!")

if __name__ == "__main__":
    download_models()
