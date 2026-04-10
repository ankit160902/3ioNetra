"""
Pre-download Hugging Face models to be baked into the Docker image.
Saves models to local directories for offline use.
"""
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
    
    # 2. Reranker Model (PyTorch)
    reranker_model_name = settings.RERANKER_MODEL
    logger.info(f"Downloading & saving reranker model '{reranker_model_name}' to {reranker_path}...")
    reranker = CrossEncoder(reranker_model_name)
    reranker.save(str(reranker_path))

    # 3. Export reranker to ONNX (for faster CPU inference at runtime)
    # Wrapped in try/except — if this fails, PyTorch fallback still works
    try:
        logger.info(f"Exporting reranker to ONNX format...")
        reranker_onnx = CrossEncoder(str(reranker_path), backend="onnx")
        reranker_onnx.save(str(reranker_path))
        logger.info("✅ ONNX reranker exported successfully")
    except Exception as e:
        logger.warning(f"ONNX export failed (PyTorch fallback will be used at runtime): {e}")

    # 4. Skyfield astronomical data (panchang service)
    # Without pre-downloading, hip_main.dat (~10MB) and de421.bsp (~16MB)
    # are downloaded from the internet on EVERY container startup = 2-3 min
    # cold start delay. Baking them into the image eliminates this.
    try:
        logger.info("Pre-downloading Skyfield astronomical data for panchang service...")
        from skyfield.api import Loader
        from skyfield.data import hipparcos

        # Use jyotishganit's data directory so the library finds them at runtime
        astro_dir = base_model_dir / "skyfield_data"
        astro_dir.mkdir(parents=True, exist_ok=True)

        loader = Loader(str(astro_dir), verbose=True)
        # Download ephemeris (de421.bsp ~16MB)
        logger.info("Downloading de421.bsp ephemeris...")
        loader('de421.bsp')
        # Download Hipparcos star catalog (hip_main.dat ~10MB)
        logger.info("Downloading hip_main.dat star catalog...")
        loader.open(hipparcos.URL)

        # Also download to jyotishganit's runtime data directory (Linux: ~/.local/share/jyotishganit)
        # This is where the library looks at runtime in the Docker container.
        import os, platform
        if platform.system() == "Linux":
            jyotish_dir = os.path.expanduser("~/.local/share/jyotishganit")
        else:
            jyotish_dir = str(astro_dir)  # fallback for macOS/Windows
        os.makedirs(jyotish_dir, exist_ok=True)
        jyotish_loader = Loader(jyotish_dir, verbose=True)
        jyotish_loader('de421.bsp')
        jyotish_loader.open(hipparcos.URL)

        logger.info("✅ Skyfield astronomical data baked successfully")
    except Exception as e:
        logger.warning(f"Skyfield data pre-download failed (will download at runtime): {e}")

    logger.info("✅ All models and data baked into local directories successfully!")

if __name__ == "__main__":
    download_models()
