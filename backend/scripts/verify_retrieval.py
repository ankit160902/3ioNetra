import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from rag.pipeline import RAGPipeline

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_retrieval():
    pipeline = RAGPipeline()
    await pipeline.initialize()
    
    if not pipeline.available:
        logger.error("RAG Pipeline not available. Ensure processed_data.json exists.")
        return

    test_queries = [
        {"query": "What are the yoga sutras about?", "domain": "Patanjali Yoga Sutras"},
        {"query": "Tell me about Ayurveda and health.", "domain": "Charaka Samhita (Ayurveda)"},
        {"query": "How to practice meditation for stress?", "domain": "Meditation and Mindfulness"},
        {"query": "What is the meaning of life according to Gita?", "domain": "Bhagavad Gita"}
    ]

    print("\n" + "="*80)
    print("🚀 STARTING RAG RETRIEVAL VERIFICATION")
    print("="*80)

    for test in test_queries:
        print(f"\n🔍 Querying: '{test['query']}'")
        results = await pipeline.search(test['query'], top_k=5)
        
        found_match = False
        if not results:
            print("  ⚠️ No results found.")
            continue

        for i, res in enumerate(results):
            print(f"  {i+1}. [{res.get('scripture')}] {res.get('reference')}")
            # print(f"     Text: {res.get('text')[:150]}...")
            print(f"     Score: {res.get('score'):.4f}")
            if res.get('scripture') == test['domain']:
                found_match = True
        
        if found_match:
            print(f"  ✅ SUCCESS: Found highly relevant match in '{test['domain']}'")
        else:
            print(f"  ⚠️ NOTE: Did not find direct match in '{test['domain']}' in top results.")

    print("\n" + "="*80)
    print("✅ VERIFICATION COMPLETE")
    print("="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(test_retrieval())
