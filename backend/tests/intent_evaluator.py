"""
3ioNetra Intent Classification Model Comparison
=================================================
Tests Gemini 2.0 Flash, Claude Haiku, and GPT-4o-mini for intent classification
accuracy, speed, and cost using a hand-curated ground truth dataset.

Usage:
    cd backend/
    python tests/intent_evaluator.py [--limit N]

Outputs:
    tests/qa_results/intent_eval_report.md   — Comparative report
    tests/qa_results/intent_eval_results.json — Raw results
"""

import asyncio
import json
import logging
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from typing import Dict, List

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from config import settings  # noqa: E402
from services.intent_agent import IntentAgent  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qa_results")
GT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "intent_ground_truth.json")
RESULTS_FILE = os.path.join(OUTPUT_DIR, "intent_eval_results.json")
REPORT_FILE = os.path.join(OUTPUT_DIR, "intent_eval_report.md")

DELAY_BETWEEN_CALLS = 0.5

# Fields to evaluate accuracy on
ACCURACY_FIELDS = ["intent", "life_domain", "needs_direct_answer", "recommend_products", "urgency"]
REQUIRED_JSON_FIELDS = [
    "intent", "emotion", "life_domain", "entities", "urgency",
    "summary", "needs_direct_answer", "recommend_products", "product_search_keywords",
]


def load_ground_truth() -> List[Dict]:
    with open(GT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    logger.info(f"Loaded {len(data)} ground truth entries")
    return data


def _create_intent_providers():
    providers = {}

    # Gemini Flash
    try:
        from llm.providers.gemini_fast_provider import GeminiFastIntentProvider
        providers["gemini_flash"] = GeminiFastIntentProvider()
        logger.info(f"Gemini Flash ready: {providers['gemini_flash'].name}")
    except Exception as e:
        logger.warning(f"Gemini Flash unavailable: {e}")

    # Claude Haiku
    if settings.ANTHROPIC_API_KEY:
        try:
            from llm.providers.claude_haiku_provider import ClaudeHaikuIntentProvider
            providers["claude_haiku"] = ClaudeHaikuIntentProvider()
            logger.info(f"Claude Haiku ready: {providers['claude_haiku'].name}")
        except Exception as e:
            logger.warning(f"Claude Haiku unavailable: {e}")

    # GPT-4o-mini
    if settings.OPENAI_API_KEY:
        try:
            from llm.providers.openai_mini_provider import OpenAIMiniIntentProvider
            providers["openai_mini"] = OpenAIMiniIntentProvider()
            logger.info(f"GPT-4o-mini ready: {providers['openai_mini'].name}")
        except Exception as e:
            logger.warning(f"GPT-4o-mini unavailable: {e}")

    return providers


async def classify_with_provider(provider, prompt: str):
    """Run classification and return result."""
    try:
        return await provider.classify(prompt)
    except Exception as e:
        logger.error(f"Classification failed for {provider.name}: {e}")
        return None


def compute_accuracy(predictions: List[Dict], ground_truth: List[Dict], field: str) -> float:
    """Compute exact-match accuracy for a specific field."""
    correct = 0
    total = 0
    for pred, gt in zip(predictions, ground_truth):
        expected = gt["expected"].get(field)
        actual = pred.get(field)

        if expected is None:
            continue

        total += 1
        # Normalize for comparison
        if isinstance(expected, bool):
            actual_bool = actual if isinstance(actual, bool) else str(actual).lower() in ("true", "1", "yes")
            if actual_bool == expected:
                correct += 1
        elif str(actual).upper() == str(expected).upper():
            correct += 1

    return correct / total if total > 0 else 0.0


def build_confusion_matrix(predictions: List[Dict], ground_truth: List[Dict], field: str) -> Dict:
    """Build confusion matrix for a field."""
    matrix = defaultdict(lambda: defaultdict(int))
    for pred, gt in zip(predictions, ground_truth):
        expected = str(gt["expected"].get(field, "")).upper()
        actual = str(pred.get(field, "")).upper()
        matrix[expected][actual] += 1
    return {k: dict(v) for k, v in matrix.items()}


def generate_report(
    results: Dict[str, List[Dict]],
    ground_truth: List[Dict],
    active_providers: List[str],
    output_path: str,
):
    """Generate comparative markdown report."""
    total = len(ground_truth)
    lines = []
    lines.append("# 3ioNetra Intent Classification Model Comparison")
    lines.append(f"\n**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Total Test Cases**: {total}")
    lines.append(f"**Models**: {', '.join(active_providers)}")

    # Accuracy table
    lines.append("\n## Accuracy by Field")
    lines.append("")
    header = "| Field |"
    sep = "|-------|"
    for p in active_providers:
        header += f" {p} |"
        sep += "------|"
    lines.append(header)
    lines.append(sep)

    for field in ACCURACY_FIELDS:
        row = f"| {field} |"
        for p in active_providers:
            preds = results.get(p, [])
            acc = compute_accuracy(preds, ground_truth, field)
            row += f" {acc*100:.1f}% |"
        lines.append(row)

    # JSON parse success rate
    lines.append("\n## JSON Parse Success Rate")
    lines.append("")
    header = "| Model | Parse Success |"
    sep = "|-------|--------------|"
    lines.append(header)
    lines.append(sep)
    for p in active_providers:
        preds = results.get(p, [])
        success = sum(1 for pr in preds if pr.get("_parse_success", False))
        rate = success / len(preds) * 100 if preds else 0
        lines.append(f"| {p} | {rate:.1f}% ({success}/{len(preds)}) |")

    # JSON completeness (all 9 fields present)
    lines.append("\n## JSON Completeness (all 9 fields)")
    lines.append("")
    header = "| Model | Complete |"
    sep = "|-------|----------|"
    lines.append(header)
    lines.append(sep)
    for p in active_providers:
        preds = results.get(p, [])
        complete = sum(1 for pr in preds if all(f in pr for f in REQUIRED_JSON_FIELDS))
        rate = complete / len(preds) * 100 if preds else 0
        lines.append(f"| {p} | {rate:.1f}% ({complete}/{len(preds)}) |")

    # Latency
    lines.append("\n## Average Latency (ms)")
    lines.append("")
    header = "| Model | Avg | p50 | p90 |"
    sep = "|-------|-----|-----|-----|"
    lines.append(header)
    lines.append(sep)
    for p in active_providers:
        preds = results.get(p, [])
        latencies = [pr.get("_latency_ms", 0) for pr in preds if pr.get("_latency_ms", 0) > 0]
        if latencies:
            avg = sum(latencies) / len(latencies)
            sorted_l = sorted(latencies)
            p50 = sorted_l[len(sorted_l) // 2]
            p90 = sorted_l[int(len(sorted_l) * 0.9)]
            lines.append(f"| {p} | {avg:.0f} | {p50:.0f} | {p90:.0f} |")
        else:
            lines.append(f"| {p} | N/A | N/A | N/A |")

    # Average cost
    lines.append("\n## Cost per Classification")
    lines.append("")
    header = "| Model | Avg Cost ($) | Total Cost ($) |"
    sep = "|-------|-------------|---------------|"
    lines.append(header)
    lines.append(sep)
    for p in active_providers:
        preds = results.get(p, [])
        costs = [pr.get("_cost_usd", 0) for pr in preds]
        total_cost = sum(costs)
        avg_cost = total_cost / len(costs) if costs else 0
        lines.append(f"| {p} | {avg_cost:.6f} | {total_cost:.4f} |")

    # Intent confusion matrix
    lines.append("\n## Intent Confusion Matrix (per model)")
    for p in active_providers:
        preds = results.get(p, [])
        matrix = build_confusion_matrix(preds, ground_truth, "intent")
        if not matrix:
            continue
        lines.append(f"\n### {p}")
        all_labels = sorted(set(list(matrix.keys()) + [v for row in matrix.values() for v in row.keys()]))
        header = "| Expected \\ Predicted |"
        sep = "|---------------------|"
        for label in all_labels:
            header += f" {label[:8]} |"
            sep += "---------|"
        lines.append(header)
        lines.append(sep)
        for expected in all_labels:
            row = f"| {expected} |"
            for predicted in all_labels:
                count = matrix.get(expected, {}).get(predicted, 0)
                row += f" {count} |"
            lines.append(row)

    # Error analysis — top misclassifications
    lines.append("\n## Error Analysis (Sample Misclassifications)")
    for p in active_providers:
        preds = results.get(p, [])
        errors = []
        for pred, gt in zip(preds, ground_truth):
            expected_intent = str(gt["expected"].get("intent", "")).upper()
            actual_intent = str(pred.get("intent", "")).upper()
            if expected_intent != actual_intent:
                errors.append({
                    "id": gt["id"],
                    "message": gt["message"][:80],
                    "expected": expected_intent,
                    "predicted": actual_intent,
                })
        if errors:
            lines.append(f"\n### {p} — {len(errors)} errors")
            for err in errors[:10]:
                lines.append(f"- ID {err['id']}: \"{err['message']}\" — expected {err['expected']}, got {err['predicted']}")

    report_text = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    logger.info(f"Report saved to {output_path}")
    return report_text


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Intent classification model comparison")
    parser.add_argument("--limit", type=int, default=0, help="Limit entries (0=all)")
    args = parser.parse_args()

    start_time = time.time()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if not os.path.exists(GT_PATH):
        logger.error(f"Ground truth not found at {GT_PATH}")
        sys.exit(1)

    ground_truth = load_ground_truth()
    if args.limit > 0:
        ground_truth = ground_truth[:args.limit]

    providers = _create_intent_providers()
    active_providers = list(providers.keys())
    if not active_providers:
        logger.error("No intent providers available. Check API keys.")
        sys.exit(1)

    # Build the same prompt template used by IntentAgent
    intent_prompt_template = IntentAgent.INTENT_PROMPT

    # Load existing results
    existing = {}
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            existing = json.load(f)

    async def run_evaluation():
        all_results = {p: [] for p in active_providers}

        for i, entry in enumerate(ground_truth):
            eid = entry["id"]
            message = entry["message"]
            context = entry.get("context_summary", "")
            prompt = intent_prompt_template.format(message=message, context=context)

            logger.info(f"[{i+1}/{len(ground_truth)}] ID {eid}: {message[:50]}...")

            for pname, provider in providers.items():
                cache_key = f"{eid}_{pname}"
                if cache_key in existing:
                    all_results[pname].append(existing[cache_key])
                    continue

                result = await classify_with_provider(provider, prompt)

                if result is None:
                    parsed = {}
                    parsed["_parse_success"] = False
                    parsed["_latency_ms"] = 0
                    parsed["_cost_usd"] = 0
                else:
                    parsed = result.raw_json.copy()
                    parsed["_parse_success"] = result.parse_success
                    parsed["_latency_ms"] = result.latency_ms
                    parsed["_cost_usd"] = result.cost_usd
                    parsed["_input_tokens"] = result.input_tokens
                    parsed["_output_tokens"] = result.output_tokens
                    parsed["_raw_text"] = result.raw_text[:500]

                all_results[pname].append(parsed)
                existing[cache_key] = parsed

                await asyncio.sleep(DELAY_BETWEEN_CALLS)

            # Save progress
            with open(RESULTS_FILE, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)

        return all_results

    results = asyncio.run(run_evaluation())

    # Generate report
    report = generate_report(results, ground_truth, active_providers, REPORT_FILE)

    elapsed = time.time() - start_time
    logger.info(f"\nEvaluation complete in {elapsed/60:.1f} minutes")

    if report:
        print("\n" + "=" * 70)
        print(report)
        print("=" * 70)


if __name__ == "__main__":
    main()
