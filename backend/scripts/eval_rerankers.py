"""
3ioNetra Reranker Model Comparison
====================================
Evaluates reranking models by providing the same top-20 candidate set
(from current embeddings) to each reranker and measuring NDCG, MRR, latency.

Usage:
    cd backend/
    python scripts/eval_rerankers.py --models ms-marco-MiniLM-L-6-v2 bge-reranker-v2-m3
    python scripts/eval_rerankers.py --models all

Outputs:
    tests/qa_results/reranker_eval_report.md
"""

import argparse
import json
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

BACKEND_DIR = str(Path(__file__).parent.parent)
sys.path.insert(0, BACKEND_DIR)

from config import settings  # noqa: E402
from rag.model_registry import (  # noqa: E402
    RERANKER_MODELS,
    get_embedding_backend,
    get_reranker_backend,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BENCHMARK_PATH = os.path.join(BACKEND_DIR, "tests", "benchmarks", "retrieval_benchmark.json")
VERSES_PATH = os.path.join(BACKEND_DIR, "data", "processed", "verses.json")
OUTPUT_DIR = os.path.join(BACKEND_DIR, "tests", "qa_results")
REPORT_FILE = os.path.join(OUTPUT_DIR, "reranker_eval_report.md")

CANDIDATES_K = 20  # Same top-20 candidate set for all rerankers


def load_benchmark() -> List[Dict]:
    with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_corpus() -> Tuple[List[Dict], List[str]]:
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


def get_candidate_sets(
    benchmark: List[Dict],
    verses: List[Dict],
    corpus_texts: List[str],
) -> List[Dict]:
    """Retrieve top-20 candidates per query using current embedding model."""
    logger.info("Building candidate sets using current embedding model...")
    emb_name = settings.EMBEDDING_MODEL.split("/")[-1]

    # Try to match the registry name
    registry_name = "paraphrase-multilingual-mpnet-base-v2"
    for key in ["paraphrase-multilingual-mpnet-base-v2", "multilingual-e5-large", "bge-m3"]:
        if key in emb_name or emb_name in key:
            registry_name = key
            break

    backend = get_embedding_backend(registry_name)

    # Embed corpus
    corpus_vecs, _ = backend.encode_timed(corpus_texts)
    logger.info(f"Corpus embedded: {corpus_vecs.shape}")

    candidate_sets = []
    for entry in benchmark:
        query = entry["query"]
        query_vec, _ = backend.encode_timed([query])

        # Cosine similarity
        q = query_vec[0].astype("float32")
        q_norm = np.linalg.norm(q)
        if q_norm > 0:
            q = q / q_norm
        scores = corpus_vecs @ q

        top_indices = np.argsort(-scores)[:CANDIDATES_K]

        candidates = []
        for idx in top_indices:
            idx = int(idx)
            doc_text = f"{verses[idx].get('text', '')} {verses[idx].get('meaning', '')}".strip()
            candidates.append({
                "index": idx,
                "reference": verses[idx].get("reference", ""),
                "text": doc_text[:500],
                "retrieval_score": float(scores[idx]),
            })

        candidate_sets.append({
            "query": query,
            "language": entry.get("language", "en"),
            "relevant_references": set(entry.get("relevant_references", [])),
            "candidates": candidates,
        })

    return candidate_sets


def compute_metrics(ranked_refs: List[str], relevant_refs: set) -> Dict:
    metrics = {}

    # MRR
    mrr = 0.0
    for i, ref in enumerate(ranked_refs):
        if ref in relevant_refs:
            mrr = 1.0 / (i + 1)
            break
    metrics["mrr"] = mrr

    # NDCG@3
    for k in [3, 5]:
        dcg = 0.0
        for i, ref in enumerate(ranked_refs[:k]):
            rel = 1.0 if ref in relevant_refs else 0.0
            dcg += rel / np.log2(i + 2)

        ideal_rels = sorted(
            [1.0] * min(len(relevant_refs), k) + [0.0] * max(0, k - len(relevant_refs)),
            reverse=True,
        )
        idcg = sum(r / np.log2(i + 2) for i, r in enumerate(ideal_rels))
        metrics[f"ndcg@{k}"] = dcg / idcg if idcg > 0 else 0.0

    return metrics


def evaluate_reranker(
    model_name: str,
    candidate_sets: List[Dict],
) -> Dict:
    """Evaluate a single reranker on pre-computed candidate sets."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Evaluating reranker: {model_name}")
    logger.info(f"{'='*60}")

    backend = get_reranker_backend(model_name)

    all_metrics = defaultdict(list)
    per_language = defaultdict(lambda: defaultdict(list))
    latencies = []

    for cs in candidate_sets:
        query = cs["query"]
        lang = cs["language"]
        relevant_refs = cs["relevant_references"]
        candidates = cs["candidates"]

        if not candidates:
            continue

        doc_texts = [c["text"] for c in candidates]

        # Rerank
        scores, elapsed = backend.rerank_timed(query, doc_texts)
        latencies.append(elapsed * 1000)

        # Sort candidates by reranker score
        scored = list(zip(candidates, scores))
        scored.sort(key=lambda x: x[1], reverse=True)

        ranked_refs = [c["reference"] for c, _ in scored]

        metrics = compute_metrics(ranked_refs, relevant_refs)
        for k, v in metrics.items():
            all_metrics[k].append(v)
            per_language[lang][k].append(v)

    result = {
        "model": model_name,
        "avg_latency_ms": np.mean(latencies) if latencies else 0,
        "p50_latency_ms": np.percentile(latencies, 50) if latencies else 0,
        "p90_latency_ms": np.percentile(latencies, 90) if latencies else 0,
        "overall": {k: np.mean(v) for k, v in all_metrics.items()},
        "per_language": {},
    }
    for lang, lang_metrics in per_language.items():
        result["per_language"][lang] = {k: np.mean(v) for k, v in lang_metrics.items()}

    return result


def generate_report(results: List[Dict], output_path: str):
    lines = []
    lines.append("# 3ioNetra Reranker Model Comparison Report")
    lines.append(f"\n**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Models tested**: {len(results)}")
    lines.append(f"**Candidates per query**: {CANDIDATES_K}")

    metric_keys = ["ndcg@3", "ndcg@5", "mrr"]

    lines.append("\n## Overall Reranking Quality")
    lines.append("")
    header = "| Model |"
    sep = "|-------|"
    for m in metric_keys:
        header += f" {m} |"
        sep += "------|"
    lines.append(header)
    lines.append(sep)

    for r in results:
        row = f"| {r['model']} |"
        for m in metric_keys:
            val = r["overall"].get(m, 0)
            row += f" {val:.3f} |"
        lines.append(row)

    # Latency
    lines.append("\n## Latency (ms per query)")
    lines.append("")
    lines.append("| Model | Avg | p50 | p90 |")
    lines.append("|-------|-----|-----|-----|")
    for r in results:
        lines.append(
            f"| {r['model']} | {r['avg_latency_ms']:.1f} | "
            f"{r['p50_latency_ms']:.1f} | {r['p90_latency_ms']:.1f} |"
        )

    # Per-language
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

    if results:
        best = max(results, key=lambda r: r["overall"].get("ndcg@5", 0))
        lines.append(f"\n## Recommendation")
        lines.append(f"\nBest overall reranker by NDCG@5: **{best['model']}** ({best['overall'].get('ndcg@5', 0):.3f})")

    report_text = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    logger.info(f"Report saved to {output_path}")
    return report_text


def main():
    parser = argparse.ArgumentParser(description="Reranker model comparison")
    parser.add_argument(
        "--models", nargs="+", default=["ms-marco-MiniLM-L-6-v2"],
        help="Reranker model names (or 'all')",
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

    # Build candidate sets using current embedding model (same for all rerankers)
    candidate_sets = get_candidate_sets(benchmark, verses, corpus_texts)

    model_names = list(RERANKER_MODELS.keys()) if "all" in args.models else args.models

    results = []
    for model_name in model_names:
        try:
            result = evaluate_reranker(model_name, candidate_sets)
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
