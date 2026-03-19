"""
Benchmark: Hybrid RAG vs Baseline Retrieval

Runs 100 benchmark queries through both baseline (rag_pipeline.search) and
enhanced (retrieval_judge.enhanced_retrieve) paths, comparing Hit@3, MRR,
and avg latency.

Requires:
  - backend/data/processed/verses.json + embeddings.npy
  - GEMINI_API_KEY in environment (for LLM calls in judge)

Usage:
    cd backend && python tests/benchmark_hybrid_rag.py
"""

import asyncio
import json
import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def _hit_at_k(results, relevant_refs, k=3, match_mode="scripture_level"):
    """Check if any of the top-k results match a relevant reference."""
    for doc in results[:k]:
        ref = doc.get("reference", "")
        scripture = doc.get("scripture", "")
        for rel in relevant_refs:
            if match_mode == "scripture_level":
                # Match if scripture name appears in reference or scripture field
                rel_lower = rel.lower()
                if rel_lower in ref.lower() or rel_lower in scripture.lower():
                    return 1.0
            else:
                # Exact reference match
                if rel.lower() == ref.lower():
                    return 1.0
    return 0.0


def _mrr(results, relevant_refs, match_mode="scripture_level"):
    """Mean Reciprocal Rank: 1/rank of first relevant result."""
    for rank, doc in enumerate(results, 1):
        ref = doc.get("reference", "")
        scripture = doc.get("scripture", "")
        for rel in relevant_refs:
            if match_mode == "scripture_level":
                rel_lower = rel.lower()
                if rel_lower in ref.lower() or rel_lower in scripture.lower():
                    return 1.0 / rank
            else:
                if rel.lower() == ref.lower():
                    return 1.0 / rank
    return 0.0


async def run_benchmark():
    benchmark_path = Path(__file__).parent / "benchmarks" / "retrieval_benchmark_100.json"
    if not benchmark_path.exists():
        print(f"Benchmark file not found: {benchmark_path}")
        sys.exit(1)

    with open(benchmark_path) as f:
        queries = json.load(f)

    print(f"Loaded {len(queries)} benchmark queries")

    # Initialize RAG pipeline
    from rag.pipeline import get_rag_pipeline
    rag = get_rag_pipeline()
    if not rag or not rag.available:
        print("RAG pipeline not available. Ensure data/processed/ files exist.")
        sys.exit(1)

    # Initialize judge
    from services.retrieval_judge import get_retrieval_judge
    judge = get_retrieval_judge()

    print(f"RAG available: {rag.available}")
    print(f"Judge available: {judge.available}")
    print(f"LLM available: {judge.llm.available if judge.llm else False}")
    print()

    # Run benchmarks
    baseline_hits = []
    baseline_mrrs = []
    baseline_times = []
    enhanced_hits = []
    enhanced_mrrs = []
    enhanced_times = []
    per_query_results = []

    for i, q in enumerate(queries):
        query_text = q["query"]
        relevant = q.get("relevant_references", [])
        match_mode = q.get("match_mode", "scripture_level")
        language = q.get("language", "en")
        search_kwargs = {"language": language, "top_k": 5}
        intent = {"intent": "SEEKING_GUIDANCE", "needs_direct_answer": True}

        # Baseline
        t0 = time.time()
        try:
            baseline_docs = await rag.search(query=query_text, **search_kwargs)
        except Exception as e:
            print(f"  [{i+1}] Baseline search failed: {e}")
            baseline_docs = []
        baseline_time = time.time() - t0

        b_hit = _hit_at_k(baseline_docs, relevant, k=3, match_mode=match_mode)
        b_mrr = _mrr(baseline_docs, relevant, match_mode=match_mode)
        baseline_hits.append(b_hit)
        baseline_mrrs.append(b_mrr)
        baseline_times.append(baseline_time)

        # Enhanced
        t0 = time.time()
        try:
            enhanced_docs = await judge.enhanced_retrieve(
                query=query_text,
                intent_analysis=intent,
                rag_pipeline=rag,
                search_kwargs=search_kwargs,
            )
        except Exception as e:
            print(f"  [{i+1}] Enhanced search failed: {e}")
            enhanced_docs = []
        enhanced_time = time.time() - t0

        e_hit = _hit_at_k(enhanced_docs, relevant, k=3, match_mode=match_mode)
        e_mrr = _mrr(enhanced_docs, relevant, match_mode=match_mode)
        enhanced_hits.append(e_hit)
        enhanced_mrrs.append(e_mrr)
        enhanced_times.append(enhanced_time)

        per_query_results.append({
            "id": q["id"],
            "query": query_text,
            "category": q.get("category", ""),
            "baseline_hit3": b_hit,
            "baseline_mrr": round(b_mrr, 4),
            "baseline_time_ms": round(baseline_time * 1000, 1),
            "enhanced_hit3": e_hit,
            "enhanced_mrr": round(e_mrr, 4),
            "enhanced_time_ms": round(enhanced_time * 1000, 1),
        })

        status = "+" if e_hit > b_hit else ("=" if e_hit == b_hit else "-")
        print(f"  [{i+1:3d}/{len(queries)}] {status} {query_text[:60]:<60}  B:{b_hit:.0f}/{b_mrr:.2f}/{baseline_time*1000:.0f}ms  E:{e_hit:.0f}/{e_mrr:.2f}/{enhanced_time*1000:.0f}ms")

    # Summary
    n = len(queries)
    b_hit3 = sum(baseline_hits) / n
    b_mrr_avg = sum(baseline_mrrs) / n
    b_lat = sum(baseline_times) / n * 1000
    e_hit3 = sum(enhanced_hits) / n
    e_mrr_avg = sum(enhanced_mrrs) / n
    e_lat = sum(enhanced_times) / n * 1000

    print()
    print("=" * 70)
    print(f"{'Metric':<25} {'Baseline':>12} {'Enhanced':>12} {'Delta':>12}")
    print("-" * 70)
    print(f"{'Hit@3':<25} {b_hit3:>11.1%} {e_hit3:>11.1%} {e_hit3-b_hit3:>+11.1%}")
    print(f"{'MRR':<25} {b_mrr_avg:>12.4f} {e_mrr_avg:>12.4f} {e_mrr_avg-b_mrr_avg:>+12.4f}")
    print(f"{'Avg Latency (ms)':<25} {b_lat:>12.1f} {e_lat:>12.1f} {e_lat-b_lat:>+12.1f}")
    print("=" * 70)

    # Save results
    output_path = Path(__file__).parent / "hybrid_rag_benchmark_results.json"
    output = {
        "summary": {
            "baseline_hit3": round(b_hit3, 4),
            "baseline_mrr": round(b_mrr_avg, 4),
            "baseline_avg_latency_ms": round(b_lat, 1),
            "enhanced_hit3": round(e_hit3, 4),
            "enhanced_mrr": round(e_mrr_avg, 4),
            "enhanced_avg_latency_ms": round(e_lat, 1),
            "total_queries": n,
        },
        "per_query": per_query_results,
    }
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    print("=" * 70)
    print("Hybrid RAG Benchmark: Baseline vs Enhanced Retrieval")
    print("=" * 70)
    asyncio.run(run_benchmark())
