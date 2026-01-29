
import asyncio
import os
import sys
from dotenv import load_dotenv

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from backend.rag.pipeline import RAGPipeline

async def test_rag():
    pipeline = RAGPipeline()
    await pipeline.initialize()
    
    if not pipeline.available:
        print("RAG Pipeline not available")
        return

    queries = [
        "it's over work for me today",
        "it's over work for me today. The user is dealing with overwork. They are currently feeling stressed. This situation relates to their work.",
        "stress and overthinking at work"
    ]
    
    for q in queries:
        print(f"\nQuery: {q}")
        results = await pipeline.search(q, top_k=2)
        print(f"Results found: {len(results)}")
        for r in results:
            print(f"- {r.get('reference')} (Score: {r.get('score'):.4f})")

if __name__ == "__main__":
    asyncio.run(test_rag())
