import os
import asyncio
import sys
from pathlib import Path
import json

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from rag.pipeline import RAGPipeline
from config import settings

async def verify_relevance():
    print("🚀 Initializing RAG Pipeline for Relevance Testing...")
    pipeline = RAGPipeline()
    await pipeline.initialize()
    
    if not pipeline.available:
        print("❌ Pipeline not available. Ensure data/processed/ exists.")
        return

    test_cases = [
        {"query": "How to deal with grief and loss?", "intent": "EXPRESSING_EMOTION"},
        {"query": "What is the meaning of Dharma in daily life?", "intent": "SEEKING_GUIDANCE"},
        {"query": "Tell me about Lord Rama's exile to the forest.", "intent": "ASKING_INFO"},
        {"query": "How can I find peace of mind through meditation?", "intent": "SEEKING_GUIDANCE"},
        {"query": "I am feeling very anxious about my career, what should I do?", "intent": "SEEKING_GUIDANCE"},
        {"query": "I am feeling very stuck in my life, I don't know my purpose.", "intent": "SEEKING_GUIDANCE"},
        {"query": "Tell me a story about Hanuman and his devotion.", "intent": "ASKING_INFO"},
        {"query": "How to perform a simple puja at home?", "intent": "SEEKING_GUIDANCE"}
    ]

    results_report = []

    for test in test_cases:
        query = test["query"]
        intent = test["intent"]
        print(f"\n🔍 Testing Query: '{query}' [Intent: {intent}]")
        results = await pipeline.search(query, top_k=3, intent=intent)
        
        query_report = {
            "query": query,
            "retrieved_verses": []
        }
        
        if not results:
            print("  ⚠️ No verses retrieved.")
        
        for i, res in enumerate(results):
            verse_text = res.get("text", "")
            meaning = res.get("meaning", "")
            translation = res.get("translation", "")
            score = res.get("score", 0.0)
            final_score = res.get("final_score", 0.0)
            scripture = res.get("scripture", "Unknown")
            ref = res.get("reference", "N/A")
            
            print(f"  [{i+1}] Score: {score:.4f} | Final: {final_score:.4f} | {scripture} ({ref})")
            print(f"      Text: {verse_text[:100]}...")
            if meaning:
                print(f"      Meaning: {meaning[:100]}...")
            
            query_report["retrieved_verses"].append({
                "rank": i + 1,
                "score": score,
                "final_score": final_score,
                "scripture": scripture,
                "reference": ref,
                "text": verse_text,
                "meaning": meaning,
                "translation": translation
            })
        
        results_report.append(query_report)

    # Save results to a file for review - fix path
    output_path = Path(__file__).parent / "relevance_test_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results_report, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Relevance test complete. Results saved to {output_path}")

if __name__ == "__main__":
    # Ensure we are in the backend directory context if needed
    # (The script adjusts sys.path, so it should be fine if run from project root)
    asyncio.run(verify_relevance())
