"""
3ioNetra Multi-Model Response Evaluator
========================================
Compares Gemini 2.5 Pro, Claude Sonnet, and GPT-4o on the same 240-question
QA dataset. Evaluates quality (5 LLM-judge dimensions), speed, and cost.

Usage:
    cd backend/
    python tests/multi_model_evaluator.py [--limit N]

Outputs:
    tests/qa_results/multi_model_responses.json   — Raw responses per model
    tests/qa_results/multi_model_report.md         — Comparative report
"""

import asyncio
import csv
import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Dict, List

# Add backend to path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from config import settings  # noqa: E402
from models.session import ConversationPhase  # noqa: E402
from services.prompt_manager import PromptManager  # noqa: E402
from tests.eval_utils import run_format_checks, call_llm_judge  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────

QA_CSV_PATH = os.path.expanduser(
    "~/Downloads/spiritual_companion_eval_dataset(QA_Dataset).csv"
)
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qa_results")
RESPONSES_FILE = os.path.join(OUTPUT_DIR, "multi_model_responses.json")
REPORT_FILE = os.path.join(OUTPUT_DIR, "multi_model_report.md")

DELAY_BETWEEN_QUESTIONS = 1.5
JUDGE_DELAY = 1.0

PROVIDER_NAMES = ["gemini", "claude", "openai"]

_QA_JUDGE_PROMPT = """You are an expert evaluator for a spiritual companion AI chatbot (3ioNetra — Mitra) rooted in Sanatana Dharma.

Score the bot's RESPONSE to the user's question on these 5 dimensions (1-5 scale each):

1. **tone_match** (1-5): Does the response tone match the expected tone? Expected tone: "{tone_guide}"
2. **dharmic_integration** (1-5): Does it naturally weave in the dharmic principle? Expected: "{dharmic_principle}"
3. **practice_specificity** (1-5): Are suggestions concrete and actionable? Expected practice type: "{suggested_practice}"
4. **conversational_flow** (1-5): Does it read like a warm, knowledgeable friend?
5. **overall_quality** (1-5): Holistic quality compared to what an ideal spiritual companion would say.

USER'S QUESTION:
{question}

USER CONTEXT: {user_context} ({life_stage})

BOT'S RESPONSE:
{response}

REFERENCE ANSWER (for comparison, not exact match):
{reference_answer}

Respond with ONLY a valid JSON object (no markdown, no code fences):
{{"tone_match": <1-5>, "dharmic_integration": <1-5>, "practice_specificity": <1-5>, "conversational_flow": <1-5>, "overall_quality": <1-5>, "notes": "<brief 1-2 sentence evaluation note>"}}"""

_JUDGE_KEYS = ["tone_match", "dharmic_integration", "practice_specificity", "conversational_flow", "overall_quality"]


# ─────────────────────────────────────────────────────────
# CSV Loader
# ─────────────────────────────────────────────────────────

def load_qa_dataset(csv_path: str) -> List[Dict]:
    rows = []
    with open(csv_path, "r", encoding="cp1252") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    logger.info(f"Loaded {len(rows)} QA entries")
    return rows


def build_user_profile(life_stage: str) -> Dict:
    stage_map = {
        "Teen": {"age_group": "13-17", "profession": "student"},
        "Student": {"age_group": "16-20", "profession": "student"},
        "College": {"age_group": "18-22", "profession": "college student"},
        "Young Adult": {"age_group": "22-28"},
        "Young Professional": {"age_group": "24-30", "profession": "working professional"},
        "Working Professional": {"age_group": "28-40", "profession": "working professional"},
        "Married": {"age_group": "28-45"},
        "Any": {},
    }
    return stage_map.get(life_stage, {})


# ─────────────────────────────────────────────────────────
# Provider Factory
# ─────────────────────────────────────────────────────────

def _create_providers():
    providers = {}

    # Gemini
    try:
        from llm.providers.gemini_provider import GeminiResponseProvider
        providers["gemini"] = GeminiResponseProvider()
        logger.info(f"Gemini provider ready: {providers['gemini'].name}")
    except Exception as e:
        logger.warning(f"Gemini provider unavailable: {e}")

    # Claude
    if settings.ANTHROPIC_API_KEY:
        try:
            from llm.providers.claude_provider import ClaudeResponseProvider
            providers["claude"] = ClaudeResponseProvider()
            logger.info(f"Claude provider ready: {providers['claude'].name}")
        except Exception as e:
            logger.warning(f"Claude provider unavailable: {e}")

    # OpenAI
    if settings.OPENAI_API_KEY:
        try:
            from llm.providers.openai_provider import OpenAIResponseProvider
            providers["openai"] = OpenAIResponseProvider()
            logger.info(f"OpenAI provider ready: {providers['openai'].name}")
        except Exception as e:
            logger.warning(f"OpenAI provider unavailable: {e}")

    return providers


# ─────────────────────────────────────────────────────────
# Per-Question Evaluation
# ─────────────────────────────────────────────────────────

async def evaluate_question(
    providers: Dict,
    question: str,
    system_instruction: str,
    phase_instructions: str,
    user_profile: Dict,
) -> Dict:
    """Run all providers on a single question in parallel."""
    tasks = {}
    for pname, provider in providers.items():
        tasks[pname] = provider.generate(
            query=question,
            system_instruction=system_instruction,
            phase_instructions=phase_instructions,
            user_profile=user_profile,
        )

    results = {}
    gathered = await asyncio.gather(*tasks.values(), return_exceptions=True)

    for pname, result in zip(tasks.keys(), gathered):
        if isinstance(result, Exception):
            logger.error(f"  {pname} failed: {result}")
            results[pname] = {
                "text": f"[ERROR] {str(result)[:200]}",
                "latency_ms": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0,
            }
        else:
            results[pname] = {
                "text": result.text,
                "latency_ms": result.latency_ms,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "cost_usd": result.cost_usd,
            }

    return results


# ─────────────────────────────────────────────────────────
# Report Generator
# ─────────────────────────────────────────────────────────

def _percentile(values: List[float], p: int) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = int(len(sorted_vals) * p / 100)
    idx = min(idx, len(sorted_vals) - 1)
    return sorted_vals[idx]


def generate_report(all_results: List[Dict], active_providers: List[str], output_path: str):
    """Generate comparative markdown report."""
    total = len(all_results)
    if total == 0:
        return

    lines = []
    lines.append("# 3ioNetra Multi-Model Comparison Report")
    lines.append(f"\n**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Total Questions**: {total}")
    lines.append(f"**Models**: {', '.join(active_providers)}")

    score_keys = _JUDGE_KEYS

    # Per-model aggregate scores
    lines.append("\n## Overall Scores (Mean across all questions)")
    lines.append("")
    header = "| Dimension |"
    sep = "|-----------|"
    for p in active_providers:
        header += f" {p} |"
        sep += "------|"
    lines.append(header)
    lines.append(sep)

    model_composites = {}
    for key in score_keys:
        row = f"| {key.replace('_', ' ').title()} |"
        for p in active_providers:
            vals = [
                r.get(f"judge_{p}", {}).get(key, 0)
                for r in all_results
                if r.get(f"judge_{p}", {}).get(key, 0) > 0
            ]
            mean = sum(vals) / len(vals) if vals else 0
            model_composites.setdefault(p, []).append(mean)
            row += f" **{mean:.2f}** |"
        lines.append(row)

    row = "| **Composite** |"
    for p in active_providers:
        comp = sum(model_composites.get(p, [])) / len(score_keys) if model_composites.get(p) else 0
        row += f" **{comp:.2f}** |"
    lines.append(row)

    # Latency percentiles
    lines.append("\n## Latency (ms)")
    lines.append("")
    header = "| Percentile |"
    sep = "|-----------|"
    for p in active_providers:
        header += f" {p} |"
        sep += "------|"
    lines.append(header)
    lines.append(sep)

    for pct in [50, 90, 99]:
        row = f"| p{pct} |"
        for p in active_providers:
            latencies = [r.get(f"response_{p}", {}).get("latency_ms", 0) for r in all_results]
            latencies = [l for l in latencies if l > 0]
            row += f" {_percentile(latencies, pct):.0f} |"
        lines.append(row)

    # Cost analysis
    lines.append("\n## Cost Analysis")
    lines.append("")
    header = "| Metric |"
    sep = "|--------|"
    for p in active_providers:
        header += f" {p} |"
        sep += "------|"
    lines.append(header)
    lines.append(sep)

    row = "| Total cost ($) |"
    for p in active_providers:
        total_cost = sum(r.get(f"response_{p}", {}).get("cost_usd", 0) for r in all_results)
        row += f" {total_cost:.4f} |"
    lines.append(row)

    row = "| Avg cost/question ($) |"
    for p in active_providers:
        costs = [r.get(f"response_{p}", {}).get("cost_usd", 0) for r in all_results]
        avg = sum(costs) / len(costs) if costs else 0
        row += f" {avg:.6f} |"
    lines.append(row)

    # Format compliance
    lines.append("\n## Format Compliance (Pass Rate %)")
    lines.append("")
    format_checks = [
        "no_bullet_points", "no_numbered_lists", "no_markdown_headers",
        "no_hollow_phrases", "no_formulaic_endings", "verse_tag_compliance",
        "response_length",
    ]
    header = "| Check |"
    sep = "|-------|"
    for p in active_providers:
        header += f" {p} |"
        sep += "------|"
    lines.append(header)
    lines.append(sep)

    for check in format_checks:
        row = f"| {check.replace('_', ' ').title()} |"
        for p in active_providers:
            passed = sum(
                1 for r in all_results
                if r.get(f"format_{p}", {}).get(check, {}).get("passed", False)
            )
            rate = passed / total * 100 if total else 0
            row += f" {rate:.1f}% |"
        lines.append(row)

    # Head-to-head
    if len(active_providers) >= 2:
        lines.append("\n## Head-to-Head Wins (by overall_quality)")
        lines.append("")
        for i, p1 in enumerate(active_providers):
            for p2 in active_providers[i + 1:]:
                p1_wins = 0
                p2_wins = 0
                ties = 0
                for r in all_results:
                    s1 = r.get(f"judge_{p1}", {}).get("overall_quality", 0)
                    s2 = r.get(f"judge_{p2}", {}).get("overall_quality", 0)
                    if s1 > s2:
                        p1_wins += 1
                    elif s2 > s1:
                        p2_wins += 1
                    else:
                        ties += 1
                lines.append(f"- **{p1} vs {p2}**: {p1_wins} / {p2_wins} / {ties} (wins/losses/ties)")

    report_text = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    logger.info(f"Report saved to {output_path}")
    return report_text


# ─────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Multi-model response evaluator")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of questions (0=all)")
    args = parser.parse_args()

    start_time = time.time()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if not os.path.exists(QA_CSV_PATH):
        logger.error(f"QA dataset not found at {QA_CSV_PATH}")
        sys.exit(1)

    dataset = load_qa_dataset(QA_CSV_PATH)
    if args.limit > 0:
        dataset = dataset[:args.limit]
    logger.info(f"Evaluating {len(dataset)} questions")

    # Load system instruction from YAML
    prompt_dir = os.path.join(BACKEND_DIR, "prompts")
    pm = PromptManager(prompt_dir)
    system_instruction = pm.get_prompt("spiritual_mitra", "system_instruction")
    if not system_instruction:
        logger.error("Could not load system_instruction from spiritual_mitra.yaml")
        sys.exit(1)

    phase_instructions = pm.get_prompt("spiritual_mitra", f"phase_prompts.{ConversationPhase.GUIDANCE.value}", default="")

    # Initialize providers
    providers = _create_providers()
    active_providers = list(providers.keys())
    if not active_providers:
        logger.error("No providers available. Check API keys.")
        sys.exit(1)
    logger.info(f"Active providers: {active_providers}")

    # Initialize Gemini judge client
    from google import genai
    judge_client = genai.Client(api_key=settings.GEMINI_API_KEY)

    # Load existing results for resumability
    existing = {}
    if os.path.exists(RESPONSES_FILE):
        with open(RESPONSES_FILE, "r", encoding="utf-8") as f:
            existing = json.load(f)
        logger.info(f"Loaded {len(existing)} existing results (resuming)")

    # Phase 1: Generate responses from all models
    logger.info("=" * 60)
    logger.info("PHASE 1: Generating responses from all models")
    logger.info("=" * 60)

    async def run_all():
        for i, row in enumerate(dataset):
            qid = str(row.get("ID", i + 1))

            if qid in existing and all(f"response_{p}" in existing[qid] for p in active_providers):
                logger.info(f"[{i+1}/{len(dataset)}] ID {qid} — cached, skipping")
                continue

            question = row.get("User_Question", "")
            life_stage = row.get("Life_Stage", "Any")
            user_profile = build_user_profile(life_stage)

            logger.info(f"[{i+1}/{len(dataset)}] ID {qid} — {row.get('Primary_Category', '')}")

            results = await evaluate_question(
                providers, question, system_instruction, phase_instructions, user_profile
            )

            entry = existing.get(qid, {})
            for pname, result in results.items():
                entry[f"response_{pname}"] = result
            existing[qid] = entry

            with open(RESPONSES_FILE, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)

            await asyncio.sleep(DELAY_BETWEEN_QUESTIONS)

    asyncio.run(run_all())
    logger.info("Phase 1 complete")

    # Phase 2: Format checks + LLM-as-Judge for all responses
    logger.info("=" * 60)
    logger.info("PHASE 2: Format checks + LLM-as-Judge")
    logger.info("=" * 60)

    all_results = []
    for i, row in enumerate(dataset):
        qid = str(row.get("ID", i + 1))
        entry = existing.get(qid, {})
        result_row = {"ID": qid, "Primary_Category": row.get("Primary_Category", ""), "User_Question": row.get("User_Question", "")}

        for pname in active_providers:
            resp_data = entry.get(f"response_{pname}", {})
            response_text = resp_data.get("text", "")
            result_row[f"response_{pname}"] = resp_data

            # Format checks
            fmt = run_format_checks(response_text, safety_flag=row.get("Safety_Flag", "standard"))
            result_row[f"format_{pname}"] = fmt

            # Judge
            judge_key = f"judge_{pname}"
            if judge_key in entry:
                result_row[judge_key] = entry[judge_key]
            elif response_text.startswith("[ERROR]"):
                result_row[judge_key] = {k: 0 for k in _JUDGE_KEYS}
                result_row[judge_key]["notes"] = "Response generation failed"
            else:
                logger.info(f"  Judging {pname} for ID {qid}...")
                prompt = _QA_JUDGE_PROMPT.format(
                    tone_guide=row.get("Tone_Guide", ""),
                    dharmic_principle=row.get("Dharmic_Principle", ""),
                    suggested_practice=row.get("Suggested_Practice", ""),
                    question=row.get("User_Question", ""),
                    user_context=row.get("User_Context", ""),
                    life_stage=row.get("Life_Stage", ""),
                    response=response_text[:2000],
                    reference_answer=row.get("Reference_Answer", "")[:500],
                )
                scores = call_llm_judge(judge_client, prompt, _JUDGE_KEYS)
                result_row[judge_key] = scores
                entry[judge_key] = scores
                time.sleep(JUDGE_DELAY)

        existing[qid] = entry
        all_results.append(result_row)

    # Save updated cache
    with open(RESPONSES_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    # Phase 3: Generate report
    logger.info("=" * 60)
    logger.info("PHASE 3: Generating comparative report")
    logger.info("=" * 60)

    report = generate_report(all_results, active_providers, REPORT_FILE)

    elapsed = time.time() - start_time
    logger.info(f"\nEvaluation complete in {elapsed/60:.1f} minutes")
    logger.info(f"Results: {OUTPUT_DIR}")

    if report:
        print("\n" + "=" * 70)
        print(report)
        print("=" * 70)


if __name__ == "__main__":
    main()
