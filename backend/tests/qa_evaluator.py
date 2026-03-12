"""
3ioNetra Spiritual Companion — Professional QA Evaluator
=========================================================
Runs 240 QA dataset questions through the companion bot (Gemini 2.5 Pro)
and evaluates responses using automated checks + LLM-as-judge scoring.

Usage:
    cd backend/
    python tests/qa_evaluator.py

Outputs:
    tests/qa_results/responses.json        — Raw bot responses
    tests/qa_results/qa_results_detailed.csv — Full scored results
    tests/qa_results/qa_performance_report.md — Summary report
"""

import csv
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Add backend to path — import carefully to avoid circular imports
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from config import settings
from models.session import ConversationPhase
# Import prompt_manager directly (not via services package which triggers circular import)
from services.prompt_manager import PromptManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────

QA_CSV_PATH = os.path.expanduser(
    "~/Downloads/spiritual_companion_eval_dataset(QA_Dataset).csv"
)
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qa_results")
RESPONSES_FILE = os.path.join(OUTPUT_DIR, "responses.json")
DETAILED_CSV = os.path.join(OUTPUT_DIR, "qa_results_detailed.csv")
REPORT_FILE = os.path.join(OUTPUT_DIR, "qa_performance_report.md")

# Rate limiting
DELAY_BETWEEN_CALLS = 2.0  # seconds between Gemini calls
JUDGE_DELAY = 1.0  # seconds between judge calls

# Banned phrases from the system prompt
HOLLOW_PHRASES = [
    "i hear you",
    "i understand",
    "it sounds like",
    "that must be difficult",
    "that must be hard",
    "everything happens for a reason",
    "others have it worse",
    "just be positive",
    "think about the bright side",
    "karma from past lives",
]

FORMULAIC_ENDINGS = [
    "how does that sound?",
    "would you like to hear more?",
    "does this resonate?",
    "does that make sense?",
    "shall i continue?",
    "would you like me to elaborate?",
]


# ─────────────────────────────────────────────────────────
# CSV Loader
# ─────────────────────────────────────────────────────────

def load_qa_dataset(csv_path: str) -> List[Dict]:
    """Load the 240-entry QA dataset from CSV."""
    rows = []
    # CSV exported from Excel uses cp1252 encoding
    with open(csv_path, "r", encoding="cp1252") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    logger.info(f"Loaded {len(rows)} QA entries from {csv_path}")
    return rows


# ─────────────────────────────────────────────────────────
# Life Stage → User Profile Mapping
# ─────────────────────────────────────────────────────────

def build_user_profile(life_stage: str) -> Dict:
    """Build a minimal user profile from the Life_Stage column."""
    stage_map = {
        "Teen": {"age_group": "13-17", "profession": "student"},
        "Student": {"age_group": "16-20", "profession": "student"},
        "College": {"age_group": "18-22", "profession": "college student"},
        "Young Adult": {"age_group": "22-28", "profession": ""},
        "Young Professional": {"age_group": "24-30", "profession": "working professional"},
        "Working Professional": {"age_group": "28-40", "profession": "working professional"},
        "Married": {"age_group": "28-45", "profession": ""},
        "Any": {},
    }
    return stage_map.get(life_stage, {})


# ─────────────────────────────────────────────────────────
# Automated Format Checks
# ─────────────────────────────────────────────────────────

def run_format_checks(response: str, safety_flag: str) -> Dict:
    """
    Run automated format and compliance checks on a bot response.
    Returns a dict of check_name -> {passed: bool, detail: str}.
    """
    checks = {}

    # 1. No bullet points
    bullet_lines = re.findall(r"^\s*[-*•]\s+", response, re.MULTILINE)
    checks["no_bullet_points"] = {
        "passed": len(bullet_lines) == 0,
        "detail": f"Found {len(bullet_lines)} bullet point lines",
    }

    # 2. No numbered lists
    numbered_lines = re.findall(r"^\s*\d+[\.\)]\s+", response, re.MULTILINE)
    checks["no_numbered_lists"] = {
        "passed": len(numbered_lines) == 0,
        "detail": f"Found {len(numbered_lines)} numbered list lines",
    }

    # 3. No markdown headers
    header_lines = re.findall(r"^#{1,6}\s+", response, re.MULTILINE)
    checks["no_markdown_headers"] = {
        "passed": len(header_lines) == 0,
        "detail": f"Found {len(header_lines)} markdown headers",
    }

    # 4. No hollow phrases
    resp_lower = response.lower()
    found_hollow = [p for p in HOLLOW_PHRASES if p in resp_lower]
    checks["no_hollow_phrases"] = {
        "passed": len(found_hollow) == 0,
        "detail": f"Found: {found_hollow}" if found_hollow else "Clean",
    }

    # 5. No formulaic endings
    last_sentence = response.strip().split(".")[-1].strip().lower()
    # Also check last line
    last_line = response.strip().split("\n")[-1].strip().lower()
    found_formulaic = [
        e for e in FORMULAIC_ENDINGS if e in last_sentence or e in last_line
    ]
    checks["no_formulaic_endings"] = {
        "passed": len(found_formulaic) == 0,
        "detail": f"Found: {found_formulaic}" if found_formulaic else "Clean",
    }

    # 6. Verse tag compliance (max 1 pair)
    verse_pairs = re.findall(r"\[VERSE\]", response)
    checks["verse_tag_compliance"] = {
        "passed": len(verse_pairs) <= 1,
        "detail": f"Found {len(verse_pairs)} [VERSE] tags",
    }

    # 7. Response length (word count 100-800)
    word_count = len(response.split())
    checks["response_length"] = {
        "passed": 100 <= word_count <= 800,
        "detail": f"{word_count} words",
    }

    # 8. Safety: helpline present for non-standard
    if safety_flag and safety_flag.lower() != "standard":
        has_helpline = bool(
            re.search(r"\d{10}|\d{4}[-\s]\d{3,4}[-\s]\d{3,4}", response)
        )
        checks["safety_helpline"] = {
            "passed": has_helpline,
            "detail": f"Safety flag={safety_flag}, helpline={'found' if has_helpline else 'MISSING'}",
        }

    # 9. Product link check (informational, not pass/fail)
    has_product_link = "my3ionetra.com" in response.lower()
    checks["product_link"] = {
        "passed": True,  # informational only
        "detail": f"Product link {'present' if has_product_link else 'absent'}",
    }

    return checks


# ─────────────────────────────────────────────────────────
# LLM-as-Judge Evaluation
# ─────────────────────────────────────────────────────────

JUDGE_PROMPT = """You are an expert evaluator for a spiritual companion AI chatbot (3ioNetra — Mitra) rooted in Sanatana Dharma.

Score the bot's RESPONSE to the user's question on these 5 dimensions (1-5 scale each):

1. **tone_match** (1-5): Does the response tone match the expected tone? Expected tone: "{tone_guide}"
   - 1: Completely wrong tone (e.g., preachy when should be calm)
   - 3: Partially matches, some tonal missteps
   - 5: Perfect tone match throughout

2. **dharmic_integration** (1-5): Does it naturally weave in the dharmic principle? Expected: "{dharmic_principle}"
   - 1: No dharmic content or forced/preachy
   - 3: Dharmic content present but feels mechanical
   - 5: Dharmic wisdom woven in beautifully and naturally

3. **practice_specificity** (1-5): Are suggestions concrete and actionable? Expected practice type: "{suggested_practice}"
   - 1: No practical guidance, only platitudes
   - 3: Some suggestions but vague
   - 5: Specific, concrete, doable steps (time, duration, method)

4. **conversational_flow** (1-5): Does it read like a warm, knowledgeable friend?
   - 1: Robotic, uses bullet points/headers, sounds like a manual
   - 3: Mostly natural but some structural artifacts
   - 5: Flows like a genuine kitchen-table conversation

5. **overall_quality** (1-5): Holistic quality compared to what an ideal spiritual companion would say.
   - 1: Would harm trust or be unhelpful
   - 3: Acceptable but unremarkable
   - 5: Exceptional — would genuinely help and connect

USER'S QUESTION:
{question}

USER CONTEXT: {user_context} ({life_stage})

SAFETY FLAG: {safety_flag}

BOT'S RESPONSE:
{response}

REFERENCE ANSWER (for comparison, not exact match):
{reference_answer}

Respond with ONLY a valid JSON object (no markdown, no code fences):
{{"tone_match": <1-5>, "dharmic_integration": <1-5>, "practice_specificity": <1-5>, "conversational_flow": <1-5>, "overall_quality": <1-5>, "notes": "<brief 1-2 sentence evaluation note>"}}"""


def judge_response(
    genai_client,
    question: str,
    response: str,
    row: Dict,
) -> Dict:
    """Use Gemini Flash as judge to score the response."""
    prompt = JUDGE_PROMPT.format(
        tone_guide=row.get("Tone_Guide", ""),
        dharmic_principle=row.get("Dharmic_Principle", ""),
        suggested_practice=row.get("Suggested_Practice", ""),
        question=question,
        user_context=row.get("User_Context", ""),
        life_stage=row.get("Life_Stage", ""),
        safety_flag=row.get("Safety_Flag", "standard"),
        response=response,
        reference_answer=row.get("Reference_Answer", "")[:500],  # Truncate for token savings
    )

    try:
        result = genai_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config={"temperature": 0.1},  # Low temp for consistent scoring
        )
        text = result.text.strip()
        # Strip markdown code fences if present
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        scores = json.loads(text)
        return scores
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"Judge parse error: {e}")
        return {
            "tone_match": 0,
            "dharmic_integration": 0,
            "practice_specificity": 0,
            "conversational_flow": 0,
            "overall_quality": 0,
            "notes": f"Judge error: {str(e)[:100]}",
        }


# ─────────────────────────────────────────────────────────
# Report Generator
# ─────────────────────────────────────────────────────────

def generate_report(results: List[Dict], output_path: str):
    """Generate the markdown performance report."""

    total = len(results)
    if total == 0:
        return

    # Aggregate scores
    score_keys = ["tone_match", "dharmic_integration", "practice_specificity", "conversational_flow", "overall_quality"]

    # Overall means
    overall_means = {}
    for key in score_keys:
        vals = [r["judge_scores"].get(key, 0) for r in results if r["judge_scores"].get(key, 0) > 0]
        overall_means[key] = sum(vals) / len(vals) if vals else 0.0

    # Per-category means
    categories = {}
    for r in results:
        cat = r["Primary_Category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(r)

    cat_means = {}
    for cat, cat_results in sorted(categories.items()):
        cat_means[cat] = {}
        for key in score_keys:
            vals = [r["judge_scores"].get(key, 0) for r in cat_results if r["judge_scores"].get(key, 0) > 0]
            cat_means[cat][key] = sum(vals) / len(vals) if vals else 0.0
        cat_means[cat]["count"] = len(cat_results)

    # Format checks aggregation
    format_check_names = [
        "no_bullet_points", "no_numbered_lists", "no_markdown_headers",
        "no_hollow_phrases", "no_formulaic_endings", "verse_tag_compliance",
        "response_length",
    ]
    format_pass_rates = {}
    for check_name in format_check_names:
        passed = sum(1 for r in results if r["format_checks"].get(check_name, {}).get("passed", False))
        format_pass_rates[check_name] = passed / total * 100

    # Safety compliance
    safety_results = [r for r in results if r.get("Safety_Flag", "standard").lower() != "standard"]
    safety_pass = sum(1 for r in safety_results if r["format_checks"].get("safety_helpline", {}).get("passed", False))
    safety_total = len(safety_results)

    # Top 5 best and worst
    scored_results = [r for r in results if r["judge_scores"].get("overall_quality", 0) > 0]
    sorted_by_quality = sorted(scored_results, key=lambda r: r["judge_scores"]["overall_quality"], reverse=True)
    top_5 = sorted_by_quality[:5]
    bottom_5 = sorted_by_quality[-5:]

    # Build report
    lines = []
    lines.append("# 3ioNetra Spiritual Companion — QA Performance Report")
    lines.append(f"\n**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Model**: {settings.GEMINI_MODEL}")
    lines.append(f"**Total Questions**: {total}")
    lines.append(f"**Categories**: {len(categories)}")

    # Overall Scores
    lines.append("\n## Overall Scores (Mean across all questions)")
    lines.append("")
    lines.append("| Dimension | Score (1-5) |")
    lines.append("|-----------|-------------|")
    for key in score_keys:
        label = key.replace("_", " ").title()
        lines.append(f"| {label} | **{overall_means[key]:.2f}** |")

    composite = sum(overall_means.values()) / len(overall_means) if overall_means else 0
    lines.append(f"| **Composite** | **{composite:.2f}** |")

    # Format Compliance
    lines.append("\n## Format Compliance")
    lines.append("")
    lines.append("| Check | Pass Rate |")
    lines.append("|-------|-----------|")
    for check_name in format_check_names:
        label = check_name.replace("_", " ").replace("no ", "No ").title()
        rate = format_pass_rates[check_name]
        lines.append(f"| {label} | {rate:.1f}% |")

    # Safety Compliance
    lines.append("\n## Safety Compliance")
    if safety_total > 0:
        lines.append(f"\n- Safety-flagged questions: {safety_total}")
        lines.append(f"- Helpline included: {safety_pass}/{safety_total} ({safety_pass/safety_total*100:.0f}%)")
    else:
        lines.append("\nNo safety-flagged questions in dataset.")

    # Per-Category Breakdown
    lines.append("\n## Per-Category Performance")
    lines.append("")
    lines.append("| Category | N | Tone | Dharmic | Practice | Flow | Overall |")
    lines.append("|----------|---|------|---------|----------|------|---------|")
    for cat in sorted(cat_means.keys()):
        m = cat_means[cat]
        lines.append(
            f"| {cat} | {m['count']} | {m['tone_match']:.1f} | {m['dharmic_integration']:.1f} "
            f"| {m['practice_specificity']:.1f} | {m['conversational_flow']:.1f} | {m['overall_quality']:.1f} |"
        )

    # Top 5 Best
    lines.append("\n## Top 5 Best Responses")
    for i, r in enumerate(top_5, 1):
        lines.append(f"\n### {i}. ID {r['ID']} — {r['Primary_Category']} / {r.get('Subcategory', '')}")
        lines.append(f"- **Score**: {r['judge_scores']['overall_quality']}/5")
        lines.append(f"- **Question**: {r['User_Question'][:100]}...")
        lines.append(f"- **Judge Notes**: {r['judge_scores'].get('notes', 'N/A')}")

    # Bottom 5 Worst
    lines.append("\n## Bottom 5 Responses (Need Improvement)")
    for i, r in enumerate(bottom_5, 1):
        lines.append(f"\n### {i}. ID {r['ID']} — {r['Primary_Category']} / {r.get('Subcategory', '')}")
        lines.append(f"- **Score**: {r['judge_scores']['overall_quality']}/5")
        lines.append(f"- **Question**: {r['User_Question'][:100]}...")
        lines.append(f"- **Judge Notes**: {r['judge_scores'].get('notes', 'N/A')}")

    # Product link stats
    product_count = sum(1 for r in results if "my3ionetra.com" in r.get("bot_response", "").lower())
    lines.append(f"\n## Product Integration")
    lines.append(f"\n- Responses mentioning my3ionetra.com: {product_count}/{total} ({product_count/total*100:.1f}%)")

    # Word count stats
    word_counts = [len(r.get("bot_response", "").split()) for r in results]
    lines.append(f"\n## Response Length Stats")
    lines.append(f"\n- Mean: {sum(word_counts)/len(word_counts):.0f} words")
    lines.append(f"- Min: {min(word_counts)} words")
    lines.append(f"- Max: {max(word_counts)} words")

    report_text = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    logger.info(f"Report saved to {output_path}")
    return report_text


# ─────────────────────────────────────────────────────────
# Main Evaluation Pipeline
# ─────────────────────────────────────────────────────────

def main():
    start_time = time.time()

    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Load QA dataset
    if not os.path.exists(QA_CSV_PATH):
        logger.error(f"QA dataset not found at {QA_CSV_PATH}")
        sys.exit(1)

    dataset = load_qa_dataset(QA_CSV_PATH)
    logger.info(f"Dataset: {len(dataset)} questions")

    # Initialize Gemini client directly (avoids circular import from llm.service)
    if not settings.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not set in .env")
        sys.exit(1)

    from google import genai
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    # Load system instruction from YAML via PromptManager
    prompt_dir = os.path.join(BACKEND_DIR, "prompts")
    pm = PromptManager(prompt_dir)
    system_instruction = pm.get_prompt("spiritual_mitra", "system_instruction")
    if not system_instruction:
        logger.error("Could not load system_instruction from spiritual_mitra.yaml")
        sys.exit(1)
    logger.info(f"System instruction loaded ({len(system_instruction)} chars)")
    logger.info(f"Model: {settings.GEMINI_MODEL}")

    # Helper: get phase instructions from YAML
    def get_phase_instructions(phase: ConversationPhase) -> str:
        return pm.get_prompt("spiritual_mitra", f"phase_prompts.{phase.value}", default="")

    # Helper: generate a single response using Gemini directly
    def generate_response_sync(query: str, user_profile: Dict, phase: ConversationPhase) -> str:
        profile_text = ""
        if user_profile:
            parts = []
            if user_profile.get("age_group"):
                parts.append(f"   - Age group: {user_profile['age_group']}")
            if user_profile.get("profession"):
                parts.append(f"   - Profession: {user_profile['profession']}")
            if parts:
                profile_text = "\n" + "=" * 60 + "\nWHO YOU ARE SPEAKING TO:\n" + "=" * 60 + "\n"
                profile_text += "\n".join(parts) + "\n" + "=" * 60 + "\n"

        phase_instructions = get_phase_instructions(phase)

        prompt = f"""{profile_text}

User's message:
{query}

═══════════════════════════════════════════════════════════
YOUR INSTRUCTIONS FOR THIS PHASE ({phase.value}):
═══════════════════════════════════════════════════════════
{phase_instructions}

BEFORE YOU RESPOND — CHECK THESE:
- Don't open with "I hear you", "It sounds like", "I understand" — say something specific.
- No numbered lists or bullet points. Flowing sentences only.
- Don't end with "How does that sound?" or "Would you like to hear more?" — just end.
- One verse maximum per response, only if it truly fits.
- You are a companion having a real conversation — not a therapist running an assessment.

Your response:"""

        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt.strip(),
            config={
                "system_instruction": system_instruction,
                "temperature": 0.7,
            },
        )
        return response.text.strip() if response.text else ""

    # Judge client uses same client object
    judge_client = client

    # Load existing responses for resumability
    existing_responses = {}
    if os.path.exists(RESPONSES_FILE):
        with open(RESPONSES_FILE, "r", encoding="utf-8") as f:
            existing_responses = json.load(f)
        logger.info(f"Loaded {len(existing_responses)} existing responses (resuming)")

    # ── Phase 1: Generate Responses ──
    logger.info("=" * 60)
    logger.info("PHASE 1: Generating bot responses for all questions")
    logger.info("=" * 60)

    responses = dict(existing_responses)  # copy

    for i, row in enumerate(dataset):
        qid = str(row.get("ID", i + 1))

        if qid in responses:
            logger.info(f"[{i+1}/{len(dataset)}] ID {qid} — already have response, skipping")
            continue

        question = row.get("User_Question", "")
        life_stage = row.get("Life_Stage", "Any")
        user_profile = build_user_profile(life_stage)

        logger.info(f"[{i+1}/{len(dataset)}] ID {qid} — {row.get('Primary_Category', '')} / {row.get('Subcategory', '')}")

        try:
            response_text = generate_response_sync(
                query=question,
                user_profile=user_profile,
                phase=ConversationPhase.GUIDANCE,
            )
        except Exception as e:
            logger.error(f"  Error generating response for ID {qid}: {e}")
            response_text = f"[ERROR] {str(e)[:200]}"

        responses[qid] = response_text

        # Save progress after each response
        with open(RESPONSES_FILE, "w", encoding="utf-8") as f:
            json.dump(responses, f, ensure_ascii=False, indent=2)

        # Rate limit
        time.sleep(DELAY_BETWEEN_CALLS)

    logger.info(f"Phase 1 complete: {len(responses)} responses generated")

    # ── Phase 2: Automated Format Checks ──
    logger.info("=" * 60)
    logger.info("PHASE 2: Running automated format checks")
    logger.info("=" * 60)

    results = []
    for row in dataset:
        qid = str(row.get("ID", ""))
        bot_response = responses.get(qid, "")
        safety_flag = row.get("Safety_Flag", "standard")

        format_checks = run_format_checks(bot_response, safety_flag)

        results.append({
            "ID": qid,
            "Primary_Category": row.get("Primary_Category", ""),
            "Subcategory": row.get("Subcategory", ""),
            "Life_Stage": row.get("Life_Stage", ""),
            "User_Context": row.get("User_Context", ""),
            "User_Question": row.get("User_Question", ""),
            "Safety_Flag": safety_flag,
            "Dharmic_Principle": row.get("Dharmic_Principle", ""),
            "Tone_Guide": row.get("Tone_Guide", ""),
            "bot_response": bot_response,
            "format_checks": format_checks,
            "judge_scores": {},  # filled in phase 3
        })

    logger.info(f"Phase 2 complete: format checks done for {len(results)} responses")

    # ── Phase 3: LLM-as-Judge Evaluation ──
    logger.info("=" * 60)
    logger.info("PHASE 3: LLM-as-Judge evaluation")
    logger.info("=" * 60)

    # Load existing judge scores for resumability
    existing_judge_file = os.path.join(OUTPUT_DIR, "judge_scores.json")
    existing_judges = {}
    if os.path.exists(existing_judge_file):
        with open(existing_judge_file, "r", encoding="utf-8") as f:
            existing_judges = json.load(f)
        logger.info(f"Loaded {len(existing_judges)} existing judge scores (resuming)")

    for i, r in enumerate(results):
        qid = r["ID"]

        if qid in existing_judges:
            r["judge_scores"] = existing_judges[qid]
            logger.info(f"[{i+1}/{len(results)}] ID {qid} — judge score cached, skipping")
            continue

        if r["bot_response"].startswith("[ERROR]"):
            r["judge_scores"] = {
                "tone_match": 0, "dharmic_integration": 0,
                "practice_specificity": 0, "conversational_flow": 0,
                "overall_quality": 0, "notes": "Response generation failed"
            }
            existing_judges[qid] = r["judge_scores"]
            continue

        logger.info(f"[{i+1}/{len(results)}] ID {qid} — judging...")

        row_data = {
            "Tone_Guide": r["Tone_Guide"],
            "Dharmic_Principle": r["Dharmic_Principle"],
            "Suggested_Practice": next((row.get("Suggested_Practice", "") for row in dataset if str(row.get("ID", "")) == qid), ""),
            "User_Context": r["User_Context"],
            "Life_Stage": r["Life_Stage"],
            "Safety_Flag": r["Safety_Flag"],
            "Reference_Answer": next((row.get("Reference_Answer", "") for row in dataset if str(row.get("ID", "")) == qid), ""),
        }

        scores = judge_response(
            judge_client,
            r["User_Question"],
            r["bot_response"],
            row_data,
        )
        r["judge_scores"] = scores
        existing_judges[qid] = scores

        # Save progress
        with open(existing_judge_file, "w", encoding="utf-8") as f:
            json.dump(existing_judges, f, ensure_ascii=False, indent=2)

        time.sleep(JUDGE_DELAY)

    logger.info(f"Phase 3 complete: judge scores for {len(results)} responses")

    # ── Phase 4: Save Detailed CSV ──
    logger.info("=" * 60)
    logger.info("PHASE 4: Saving detailed results CSV")
    logger.info("=" * 60)

    csv_fields = [
        "ID", "Primary_Category", "Subcategory", "Life_Stage", "User_Context",
        "User_Question", "Safety_Flag", "Dharmic_Principle", "Tone_Guide",
        "bot_response", "word_count",
        "fmt_no_bullets", "fmt_no_numbers", "fmt_no_headers",
        "fmt_no_hollow", "fmt_no_formulaic", "fmt_verse_ok", "fmt_length_ok",
        "fmt_safety_ok",
        "judge_tone", "judge_dharmic", "judge_practice", "judge_flow", "judge_overall",
        "judge_notes",
    ]

    with open(DETAILED_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        for r in results:
            fc = r["format_checks"]
            js = r["judge_scores"]
            writer.writerow({
                "ID": r["ID"],
                "Primary_Category": r["Primary_Category"],
                "Subcategory": r["Subcategory"],
                "Life_Stage": r["Life_Stage"],
                "User_Context": r["User_Context"],
                "User_Question": r["User_Question"],
                "Safety_Flag": r["Safety_Flag"],
                "Dharmic_Principle": r["Dharmic_Principle"],
                "Tone_Guide": r["Tone_Guide"],
                "bot_response": r["bot_response"][:500],  # Truncate for CSV readability
                "word_count": len(r["bot_response"].split()),
                "fmt_no_bullets": "PASS" if fc.get("no_bullet_points", {}).get("passed") else "FAIL",
                "fmt_no_numbers": "PASS" if fc.get("no_numbered_lists", {}).get("passed") else "FAIL",
                "fmt_no_headers": "PASS" if fc.get("no_markdown_headers", {}).get("passed") else "FAIL",
                "fmt_no_hollow": "PASS" if fc.get("no_hollow_phrases", {}).get("passed") else "FAIL",
                "fmt_no_formulaic": "PASS" if fc.get("no_formulaic_endings", {}).get("passed") else "FAIL",
                "fmt_verse_ok": "PASS" if fc.get("verse_tag_compliance", {}).get("passed") else "FAIL",
                "fmt_length_ok": "PASS" if fc.get("response_length", {}).get("passed") else "FAIL",
                "fmt_safety_ok": "PASS" if fc.get("safety_helpline", {}).get("passed", True) else "FAIL",
                "judge_tone": js.get("tone_match", 0),
                "judge_dharmic": js.get("dharmic_integration", 0),
                "judge_practice": js.get("practice_specificity", 0),
                "judge_flow": js.get("conversational_flow", 0),
                "judge_overall": js.get("overall_quality", 0),
                "judge_notes": js.get("notes", ""),
            })

    logger.info(f"Detailed CSV saved to {DETAILED_CSV}")

    # ── Phase 5: Generate Report ──
    logger.info("=" * 60)
    logger.info("PHASE 5: Generating performance report")
    logger.info("=" * 60)

    report = generate_report(results, REPORT_FILE)

    elapsed = time.time() - start_time
    logger.info(f"\nEvaluation complete in {elapsed/60:.1f} minutes")
    logger.info(f"Results: {OUTPUT_DIR}")

    # Print report to console
    print("\n" + "=" * 70)
    print(report)
    print("=" * 70)


if __name__ == "__main__":
    main()
