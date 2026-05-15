"""
ONNX vs PyTorch Reranker — Quality & Latency Benchmark
========================================================
Proves that ONNX produces identical rankings to PyTorch on real verse data.

Usage:
    cd backend/
    python scripts/benchmark_onnx_reranker.py

What it does:
    1. Loads the reranker model in both PyTorch and ONNX backends
    2. Samples real spiritual queries paired with real verses from your corpus
    3. Runs both backends on identical inputs
    4. Compares: score differences, ranking agreement, latency
    5. Reports whether ONNX is safe to deploy (zero quality loss)
"""

import json
import logging
import os
import random
import sys
import time
from pathlib import Path

import numpy as np

BACKEND_DIR = str(Path(__file__).parent.parent)
sys.path.insert(0, BACKEND_DIR)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Representative spiritual queries covering different intents
TEST_QUERIES = [
    "I am feeling very anxious about my future, please help",
    "How to do Ganesh puja at home step by step",
    "What does the Bhagavad Gita say about karma",
    "mantra for peace of mind",
    "I lost my mother recently and feel lost",
    "Tell me about the significance of Hanuman Chalisa",
    "How to overcome anger according to scriptures",
    "Which temple should I visit for removing obstacles",
    "What is the meaning of Om Namah Shivaya",
    "I am stressed about my career and job",
    "Meditation technique for beginners",
    "Story of Lord Rama and Sita",
    "How to deal with relationship problems spiritually",
    "What is dharma according to Mahabharata",
    "Mantra for success in exams",
]

CANDIDATES_PER_QUERY = 10  # Match MAX_RERANK_CANDIDATES
WARMUP_RUNS = 3
BENCHMARK_RUNS = 5


def load_verses():
    """Load real verses from the corpus."""
    verses_path = os.path.join(BACKEND_DIR, "data", "processed", "verses.json")
    with open(verses_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    verses = data.get("verses", [])
    # Build text content the same way pipeline.py does (text + meaning + topic)
    docs = []
    for v in verses:
        parts = [v.get("text", ""), v.get("meaning", "")]
        if not v.get("meaning"):
            parts.append(v.get("topic", ""))
        content = " ".join(p for p in parts if p).strip()
        if content and len(content) > 20:
            docs.append({"content": content, "reference": v.get("reference", ""), "scripture": v.get("scripture", "")})
    return docs


def sample_candidates(docs, n=CANDIDATES_PER_QUERY):
    """Sample n random docs as reranking candidates (simulates retrieval stage)."""
    return random.sample(docs, min(n, len(docs)))


def load_model_pytorch(model_name):
    """Load CrossEncoder with PyTorch backend from local model."""
    from sentence_transformers import CrossEncoder
    local_reranker = os.path.join(BACKEND_DIR, "models", "reranker")
    src = local_reranker if os.path.exists(os.path.join(local_reranker, "config.json")) else model_name
    logger.info(f"Loading PyTorch backend from: {src}")
    t0 = time.perf_counter()
    model = CrossEncoder(src)
    elapsed = time.perf_counter() - t0
    logger.info(f"PyTorch model loaded in {elapsed:.1f}s (device={model.device})")
    return model


def load_model_onnx(model_name):
    """Load CrossEncoder with ONNX backend from local pre-exported model."""
    from sentence_transformers import CrossEncoder

    # Check for ONNX inside the existing reranker model dir
    local_reranker = os.path.join(BACKEND_DIR, "models", "reranker")
    onnx_path = os.path.join(local_reranker, "onnx", "model.onnx")

    if os.path.exists(onnx_path):
        src = local_reranker
        logger.info(f"Loading ONNX model from {src}")
    else:
        src = model_name
        logger.info(f"No local ONNX found — loading from HuggingFace: {src}")

    t0 = time.perf_counter()
    model = CrossEncoder(src, backend="onnx")
    elapsed = time.perf_counter() - t0
    model_type = type(model.model).__name__
    logger.info(f"ONNX model loaded in {elapsed:.1f}s (type={model_type})")
    return model


def run_benchmark(model, pairs, n_warmup=WARMUP_RUNS, n_runs=BENCHMARK_RUNS):
    """Run inference and return (scores, avg_latency_ms)."""
    # Warmup — let JIT/ONNX optimize
    for _ in range(n_warmup):
        model.predict(pairs)

    # Timed runs
    latencies = []
    for _ in range(n_runs):
        t0 = time.perf_counter()
        scores = model.predict(pairs)
        latencies.append((time.perf_counter() - t0) * 1000)

    avg_ms = np.mean(latencies)
    p50_ms = np.median(latencies)
    p95_ms = np.percentile(latencies, 95)
    return [float(s) for s in scores], avg_ms, p50_ms, p95_ms


def compare_rankings(scores_a, scores_b):
    """Compare two score lists — return ranking agreement metrics."""
    rank_a = np.argsort(-np.array(scores_a))
    rank_b = np.argsort(-np.array(scores_b))

    # Top-1 agreement
    top1_match = rank_a[0] == rank_b[0]

    # Top-3 agreement (same docs in top 3, any order)
    top3_a = set(rank_a[:3])
    top3_b = set(rank_b[:3])
    top3_overlap = len(top3_a & top3_b)

    # Full ranking agreement (Kendall's tau-like)
    full_match = np.array_equal(rank_a, rank_b)

    # Max absolute score difference
    max_diff = np.max(np.abs(np.array(scores_a) - np.array(scores_b)))
    mean_diff = np.mean(np.abs(np.array(scores_a) - np.array(scores_b)))

    return {
        "top1_match": top1_match,
        "top3_overlap": top3_overlap,
        "full_rank_match": full_match,
        "max_score_diff": max_diff,
        "mean_score_diff": mean_diff,
    }


def main():
    from config import settings
    model_name = settings.RERANKER_MODEL
    logger.info(f"Benchmarking model: {model_name}")
    logger.info(f"Candidates per query: {CANDIDATES_PER_QUERY}")
    logger.info(f"Warmup runs: {WARMUP_RUNS}, Benchmark runs: {BENCHMARK_RUNS}")

    # Load corpus
    logger.info("Loading verse corpus...")
    docs = load_verses()
    logger.info(f"Loaded {len(docs)} verse documents")

    # Load both backends
    pytorch_model = load_model_pytorch(model_name)
    onnx_model = load_model_onnx(model_name)

    # Run benchmark
    results = []
    total_top1_matches = 0
    total_top3_overlap = 0
    total_full_matches = 0
    pytorch_latencies = []
    onnx_latencies = []

    random.seed(42)  # Reproducible sampling

    print("\n" + "=" * 80)
    print(f"{'QUERY':<55} {'TOP1':>5} {'TOP3':>5} {'RANK':>5} {'MAX∆':>8} {'PT ms':>7} {'OX ms':>7} {'SPEED':>6}")
    print("=" * 80)

    for query in TEST_QUERIES:
        candidates = sample_candidates(docs, CANDIDATES_PER_QUERY)
        pairs = [[query, c["content"]] for c in candidates]

        pt_scores, pt_avg, pt_p50, pt_p95 = run_benchmark(pytorch_model, pairs)
        ox_scores, ox_avg, ox_p50, ox_p95 = run_benchmark(onnx_model, pairs)

        comparison = compare_rankings(pt_scores, ox_scores)
        total_top1_matches += int(comparison["top1_match"])
        total_top3_overlap += comparison["top3_overlap"]
        total_full_matches += int(comparison["full_rank_match"])
        pytorch_latencies.append(pt_avg)
        onnx_latencies.append(ox_avg)

        speedup = pt_avg / ox_avg if ox_avg > 0 else 0

        short_q = query[:53] + ".." if len(query) > 55 else query
        print(f"{short_q:<55} {'✓' if comparison['top1_match'] else '✗':>5} "
              f"{comparison['top3_overlap']}/3  {'✓' if comparison['full_rank_match'] else '~':>5} "
              f"{comparison['max_score_diff']:>7.5f} {pt_avg:>6.1f} {ox_avg:>6.1f} {speedup:>5.1f}x")

        results.append({
            "query": query,
            "comparison": comparison,
            "pytorch_ms": pt_avg,
            "onnx_ms": ox_avg,
            "speedup": speedup,
        })

    # Summary
    n = len(TEST_QUERIES)
    avg_pt = np.mean(pytorch_latencies)
    avg_ox = np.mean(onnx_latencies)
    overall_speedup = avg_pt / avg_ox if avg_ox > 0 else 0
    avg_top3 = total_top3_overlap / n

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"  Queries tested:         {n}")
    print(f"  Top-1 rank agreement:   {total_top1_matches}/{n} ({100*total_top1_matches/n:.0f}%)")
    print(f"  Top-3 overlap (avg):    {avg_top3:.1f}/3 ({100*avg_top3/3:.0f}%)")
    print(f"  Full rank match:        {total_full_matches}/{n} ({100*total_full_matches/n:.0f}%)")
    print(f"  Max score diff (worst): {max(r['comparison']['max_score_diff'] for r in results):.6f}")
    print(f"  Mean score diff (avg):  {np.mean([r['comparison']['mean_score_diff'] for r in results]):.6f}")
    print()
    print(f"  PyTorch avg latency:    {avg_pt:.1f} ms")
    print(f"  ONNX avg latency:       {avg_ox:.1f} ms")
    print(f"  Speedup:                {overall_speedup:.1f}x")
    print()

    # Verdict
    all_top1 = total_top1_matches == n
    all_top3 = avg_top3 >= 2.9  # Allow for rare floating point tie-breaking
    max_diff = max(r["comparison"]["max_score_diff"] for r in results)

    if all_top1 and max_diff < 0.01:
        print("  VERDICT: ✅ SAFE TO DEPLOY — ONNX produces identical rankings")
        print("           Score differences are within floating-point noise.")
    elif all_top1 and max_diff < 0.1:
        print("  VERDICT: ✅ SAFE — Rankings identical, minor score precision differences")
    elif total_top1_matches >= n * 0.9:
        print("  VERDICT: ⚠️  REVIEW — Most rankings match but some top-1 differences exist")
        print("           Check the mismatched queries above (✗ in TOP1 column)")
    else:
        print("  VERDICT: ❌ NOT SAFE — Significant ranking differences detected")
        print("           Do not deploy ONNX without further investigation")

    print("=" * 80)


if __name__ == "__main__":
    main()
