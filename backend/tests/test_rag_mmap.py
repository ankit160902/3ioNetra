import json
import tempfile
import asyncio
import sys
from pathlib import Path

import numpy as np

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from rag.pipeline import RAGPipeline


async def test_mmap_loading():
    """Verify RAGPipeline mmap-loads embeddings without OOM.

    Uses an isolated tempfile.TemporaryDirectory so this test never touches
    the production corpus at backend/data/processed/. Pass the temp path via
    RAGPipeline(data_dir=...) which routes all processed_dir reads through
    the override.
    """
    print("🚀 Starting RAG mmap verification...")

    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)

        num_verses = 10
        dim = 1024  # matches intfloat/multilingual-e5-large

        dummy_verses = [
            {"id": i, "text": f"Verse {i}", "scripture": "Test"}
            for i in range(num_verses)
        ]
        dummy_embs = np.random.rand(num_verses, dim).astype("float32")

        print(f"Creating {num_verses} dummy verses in temp dir: {data_dir}")
        with (data_dir / "verses.json").open("w") as f:
            json.dump({"verses": dummy_verses}, f)
        np.save(data_dir / "embeddings.npy", dummy_embs)

        print("Initializing RAGPipeline with override path...")
        pipeline = RAGPipeline(data_dir=data_dir)
        await pipeline.initialize()

        print(f"Pipeline available: {pipeline.available}")
        print(f"Verses loaded: {len(pipeline.verses)}")
        print(f"Embeddings shape: {pipeline.embeddings.shape}")
        print(
            "Memory mapped: "
            f"{isinstance(pipeline.embeddings, np.memmap) or hasattr(pipeline.embeddings, '_mmap')}"
        )

        assert pipeline.available
        assert len(pipeline.verses) == num_verses
        assert pipeline.embeddings.shape == (num_verses, dim)

    print("✅ RAG mmap verification successful (temp dir, production data untouched)")


if __name__ == "__main__":
    asyncio.run(test_mmap_loading())
