"""
3ioNetra Embedding Model Comparison
=====================================
Compares embedding models for retrieval quality on multilingual spiritual texts.

Usage:
    cd backend/
    python scripts/eval_embeddings.py --models paraphrase-multilingual-mpnet-base-v2 multilingual-e5-large bge-m3
    python scripts/eval_embeddings.py --models all

Outputs:
    tests/qa_results/embedding_eval_report.md
"""

import argparse
import json
import logging
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

BACKEND_DIR = str(Path(__file__).parent.parent)
sys.path.insert(0, BACKEND_DIR)

from config import settings  # noqa: E402
from rag.model_registry import EMBEDDING_MODELS, get_embedding_backend  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BENCHMARK_PATH = os.path.join(BACKEND_DIR, "tests", "benchmarks", "retrieval_benchmark.json")
VERSES_PATH = os.path.join(BACKEND_DIR, "data", "processed", "verses.json")
OUTPUT_DIR = os.path.join(BACKEND_DIR, "tests", "qa_results")
REPORT_FILE = os.path.join(OUTPUT_DIR, "embedding_eval_report.md")


def load_benchmark() -> List[Dict]:
    with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_corpus() -> Tuple[List[Dict], List[str]]:
    """Load verse metadata and build search texts."""
    with open(VERSES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    verses = data.get("verses", [])
    texts = []
    for v in verses:
        combined = " ".join(filter(None, [
            v.get("text", ""),
            v.get("meaning", ""),
            v.get("translation", ""),
        ])).strip()
        texts.append(combined[:1000] if combined else "empty")
    return verses, texts


def _cosine_similarity(query_vec: np.ndarray, corpus_vecs: np.ndarray) -> np.ndarray:
    """Compute cosine similarity between query and all corpus vectors."""
    q = query_vec.astype("float32")
    q_norm = np.linalg.norm(q)
    if q_norm > 0:
        q = q / q_norm
    return corpus_vecs @ q


def compute_metrics(
    ranked_refs: List[str],
    relevant_refs: set,
    k_values: List[int] = [3, 5, 10],
) -> Dict:
    """Compute retrieval metrics for a single query."""
    metrics = {}

    # Recall@K
    for k in k_values:
        top_k = set(ranked_refs[:k])
        recall = len(top_k & relevant_refs) / len(relevant_refs) if relevant_refs else 0
        metrics[f"recall@{k}"] = recall

    # MRR — 1/rank of first relevant result
    mrr = 0.0
    for i, ref in enumerate(ranked_refs):
        if ref in relevant_refs:
            mrr = 1.0 / (i + 1)
            break
    metrics["mrr"] = mrr

    # NDCG@5
    dcg = 0.0
    for i, ref in enumerate(ranked_refs[:5]):
        rel = 1.0 if ref in relevant_refs else 0.0
        dcg += rel / np.log2(i + 2)

    ideal_rels = sorted([1.0] * min(len(relevant_refs), 5) + [0.0] * max(0, 5 - len(relevant_refs)), reverse=True)
    idcg = sum(r / np.log2(i + 2) for i, r in enumerate(ideal_rels))
    metrics["ndcg@5"] = dcg / idcg if idcg > 0 else 0.0

    return metrics


def evaluate_model(
    model_name: str,
    benchmark: List[Dict],
    verses: List[Dict],
    corpus_texts: List[str],
) -> Dict:
    """Evaluate a single embedding model on the benchmark."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Evaluating: {model_name}")
    logger.info(f"{'='*60}")

    backend = get_embedding_backend(model_name)

    # Embed corpus
    logger.info(f"Embedding corpus ({len(corpus_texts)} documents)...")
    corpus_vecs, corpus_time = backend.encode_timed(corpus_texts)
    logger.info(f"Corpus embedding time: {corpus_time:.1f}s")

    # Build reference lookup
    ref_to_idx = {}
    for i, v in enumerate(verses):
        ref = v.get("reference", "")
        if ref:
            ref_to_idx[ref] = i

    # Evaluate queries
    all_metrics = defaultdict(list)
    per_language = defaultdict(lambda: defaultdict(list))
    query_latencies = []

    for entry in benchmark:
        query = entry["query"]
        lang = entry.get("language", "en")
        relevant_refs = set(entry.get("relevant_references", []))

        # Embed query
        query_vec, query_time = backend.encode_timed([query])
        query_latencies.append(query_time * 1000)  # ms

        # Rank by similarity
        scores = _cosine_similarity(query_vec[0], corpus_vecs)
        top_indices = np.argsort(-scores)[:20]

        ranked_refs = []
        for idx in top_indices:
            ref = verses[int(idx)].get("reference", "")
            if ref:
                ranked_refs.append(ref)

        metrics = compute_metrics(ranked_refs, relevant_refs)

        for k, v in metrics.items():
            all_metrics[k].append(v)
            per_language[lang][k].append(v)

    # Aggregate
    result = {
        "model": model_name,
        "dim": backend.dim,
        "corpus_embed_time_s": corpus_time,
        "avg_query_latency_ms": np.mean(query_latencies) if query_latencies else 0,
        "overall": {k: np.mean(v) for k, v in all_metrics.items()},
        "per_language": {},
    }
    for lang, lang_metrics in per_language.items():
        result["per_language"][lang] = {k: np.mean(v) for k, v in lang_metrics.items()}

    return result


def generate_report(results: List[Dict], output_path: str):
    """Generate markdown report comparing all models."""
    lines = []
    lines.append("# 3ioNetra Embedding Model Comparison Report")
    lines.append(f"\n**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Models tested**: {len(results)}")

    # Overall metrics
    metric_keys = ["recall@3", "recall@5", "recall@10", "mrr", "ndcg@5"]
    lines.append("\n## Overall Retrieval Quality")
    lines.append("")
    header = "| Model | Dim |"
    sep = "|-------|-----|"
    for m in metric_keys:
        header += f" {m} |"
        sep += "------|"
    lines.append(header)
    lines.append(sep)

    for r in results:
        row = f"| {r['model']} | {r['dim']} |"
        for m in metric_keys:
            val = r["overall"].get(m, 0)
            row += f" {val:.3f} |"
        lines.append(row)

    # Latency & performance
    lines.append("\n## Performance")
    lines.append("")
    lines.append("| Model | Corpus Embed (s) | Avg Query (ms) |")
    lines.append("|-------|-----------------|----------------|")
    for r in results:
        lines.append(f"| {r['model']} | {r['corpus_embed_time_s']:.1f} | {r['avg_query_latency_ms']:.1f} |")

    # Per-language breakdown
    all_langs = sorted(set(lang for r in results for lang in r.get("per_language", {})))
    if all_langs:
        lines.append("\n## Per-Language Breakdown")
        for lang in all_langs:
            lines.append(f"\n### {lang}")
            lines.append("")
            header = "| Model |"
            sep = "|-------|"
            for m in metric_keys:
                header += f" {m} |"
                sep += "------|"
            lines.append(header)
            lines.append(sep)

            for r in results:
                lang_data = r.get("per_language", {}).get(lang, {})
                row = f"| {r['model']} |"
                for m in metric_keys:
                    val = lang_data.get(m, 0)
                    row += f" {val:.3f} |"
                lines.append(row)

    # Recommendation
    if results:
        best = max(results, key=lambda r: r["overall"].get("ndcg@5", 0))
        lines.append(f"\n## Recommendation")
        lines.append(f"\nBest overall model by NDCG@5: **{best['model']}** ({best['overall'].get('ndcg@5', 0):.3f})")

    report_text = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    logger.info(f"Report saved to {output_path}")
    return report_text


def main():
    parser = argparse.ArgumentParser(description="Embedding model comparison")
    parser.add_argument(
        "--models", nargs="+", default=["paraphrase-multilingual-mpnet-base-v2"],
        help="Model names to compare (or 'all' for all registered models)",
    )
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if not os.path.exists(BENCHMARK_PATH):
        logger.error(f"Benchmark not found at {BENCHMARK_PATH}")
        sys.exit(1)

    if not os.path.exists(VERSES_PATH):
        logger.error(f"Corpus not found at {VERSES_PATH}. Run scripts/ingest_all_data.py first.")
        sys.exit(1)

    benchmark = load_benchmark()
    verses, corpus_texts = load_corpus()
    logger.info(f"Benchmark: {len(benchmark)} queries, Corpus: {len(verses)} documents")

    model_names = list(EMBEDDING_MODELS.keys()) if "all" in args.models else args.models

    results = []
    for model_name in model_names:
        try:
            result = evaluate_model(model_name, benchmark, verses, corpus_texts)
            results.append(result)
        except Exception as e:
            logger.error(f"Failed to evaluate {model_name}: {e}")

    if results:
        report = generate_report(results, REPORT_FILE)
        print("\n" + "=" * 70)
        print(report)
        print("=" * 70)


if __name__ == "__main__":
    main()
