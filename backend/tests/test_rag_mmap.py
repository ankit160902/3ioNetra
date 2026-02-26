import os
import json
import numpy as np
import asyncio
from pathlib import Path
import sys

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from rag.pipeline import RAGPipeline

async def test_mmap_loading():
    print("🚀 Starting RAG mmap verification...")
    
    # 1. Create dummy data
    data_dir = Path("data/processed")
    data_dir.mkdir(parents=True, exist_ok=True)
    
    meta_file = data_dir / "verses.json"
    emb_file = data_dir / "embeddings.npy"
    
    num_verses = 10
    dim = 768
    
    dummy_verses = [{"id": i, "text": f"Verse {i}", "scripture": "Test"} for i in range(num_verses)]
    dummy_embs = np.random.rand(num_verses, dim).astype("float32")
    
    print(f"Creating {num_verses} dummy verses...")
    with open(meta_file, "w") as f:
        json.dump({"verses": dummy_verses}, f)
    
    np.save(emb_file, dummy_embs)
    
    # 2. Test Pipeline
    print("Initializing RAGPipeline...")
    pipeline = RAGPipeline()
    await pipeline.initialize()
    
    print(f"Pipeline available: {pipeline.available}")
    print(f"Verses loaded: {len(pipeline.verses)}")
    print(f"Embeddings shape: {pipeline.embeddings.shape}")
    print(f"Memory mapped: {isinstance(pipeline.embeddings, np.memmap) or hasattr(pipeline.embeddings, '_mmap')}")
    
    assert pipeline.available
    assert len(pipeline.verses) == num_verses
    assert pipeline.embeddings.shape == (num_verses, dim)
    
    print("✅ RAG mmap verification successful!")

if __name__ == "__main__":
    asyncio.run(test_mmap_loading())
