"""
3ioNetra Spiritual Companion — CSV Dataset Evaluator
=====================================================
Samples 100 diverse questions from the 50K spiritual AI training dataset,
generates bot responses via Gemini, and evaluates them against expected
values (gita_reference, recommended_mantra, recommended_practice) plus
format checks and LLM-as-judge scoring.

Usage:
    cd backend/
    python tests/csv_dataset_evaluator.py

Outputs:
    tests/qa_results/csv_responses.json      — Raw bot responses (resumable)
    tests/qa_results/csv_judge_scores.json   — Judge scores (resumable)
    tests/qa_results/csv_eval_detailed.csv   — Full scored results
    tests/qa_results/csv_eval_report.md      — Summary report
"""

import csv
import json
import logging
import math
import os
import random
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Add backend to path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from config import settings
from models.session import ConversationPhase
from services.prompt_manager import PromptManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────

CSV_PATH = os.path.expanduser(
    "~/Downloads/spiritual_ai_50000_dataset (1)(Spiritual_AI_Training).csv"
)
SAMPLE_SIZE = 100
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qa_results")
RESPONSES_FILE = os.path.join(OUTPUT_DIR, "csv_responses.json")
JUDGE_SCORES_FILE = os.path.join(OUTPUT_DIR, "csv_judge_scores.json")
DETAILED_CSV = os.path.join(OUTPUT_DIR, "csv_eval_detailed.csv")
REPORT_FILE = os.path.join(OUTPUT_DIR, "csv_eval_report.md")
SAMPLE_FILE = os.path.join(OUTPUT_DIR, "csv_sample_ids.json")

DELAY_BETWEEN_CALLS = 2.0
JUDGE_DELAY = 1.0

HOLLOW_PHRASES = [
    "i hear you", "i understand", "it sounds like",
    "that must be difficult", "that must be hard",
    "everything happens for a reason", "others have it worse",
    "just be positive", "think about the bright side",
    "karma from past lives",
]

FORMULAIC_ENDINGS = [
    "how does that sound?", "would you like to hear more?",
    "does this resonate?", "does that make sense?",
    "shall i continue?", "would you like me to elaborate?",
]


# ─────────────────────────────────────────────────────────
# CSV Loading & Stratified Sampling
# ─────────────────────────────────────────────────────────

def load_csv(csv_path: str) -> List[Dict]:
    """Load the full 50K CSV dataset."""
    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            row["_row_id"] = str(i + 1)
            rows.append(row)
    logger.info(f"Loaded {len(rows)} rows from {csv_path}")
    return rows


def stratified_sample(rows: List[Dict], n: int, seed: int = 42) -> List[Dict]:
    """
    Stratified sample across problem_category to ensure coverage.
    Proportional allocation: each category gets ceil(n * category_count / total).
    """
    random.seed(seed)

    # Group by category
    by_category: Dict[str, List[Dict]] = defaultdict(list)
    for row in rows:
        by_category[row.get("problem_category", "Unknown")].append(row)

    total = len(rows)
    sampled = []

    # Proportional allocation
    allocations = {}
    remaining = n
    cats_sorted = sorted(by_category.keys())
    for cat in cats_sorted:
        count = len(by_category[cat])
        alloc = max(1, math.floor(n * count / total))
        allocations[cat] = alloc

    # Adjust to hit exactly n
    allocated_sum = sum(allocations.values())
    if allocated_sum < n:
        # Distribute remainder to largest categories
        diff = n - allocated_sum
        for cat in sorted(cats_sorted, key=lambda c: len(by_category[c]), reverse=True):
            if diff <= 0:
                break
            allocations[cat] += 1
            diff -= 1
    elif allocated_sum > n:
        diff = allocated_sum - n
        for cat in sorted(cats_sorted, key=lambda c: len(by_category[c])):
            if diff <= 0:
                break
            if allocations[cat] > 1:
                allocations[cat] -= 1
                diff -= 1

    # Sample from each category
    for cat in cats_sorted:
        pool = by_category[cat]
        k = min(allocations[cat], len(pool))
        chosen = random.sample(pool, k)
        sampled.extend(chosen)

    random.shuffle(sampled)
    logger.info(f"Stratified sample: {len(sampled)} rows across {len(allocations)} categories")
    for cat in cats_sorted:
        logger.info(f"  {cat}: {allocations[cat]} sampled from {len(by_category[cat])}")

    return sampled


# ─────────────────────────────────────────────────────────
# User Profile Mapping
# ─────────────────────────────────────────────────────────

LIFE_STAGE_PROFESSION = {
    "Teen / School": "student",
    "College": "college student",
    "Early Career": "working professional",
    "Marriage / Family": "",
    "Midlife": "working professional",
    "Pre-retirement": "",
    "Elder / Spiritual": "retired",
}


def build_user_profile(row: Dict) -> Dict:
    """Build user profile from CSV demographics."""
    return {
        "age_group": row.get("user_age", ""),
        "gender": row.get("user_gender", ""),
        "profession": LIFE_STAGE_PROFESSION.get(row.get("life_stage", ""), ""),
        "life_stage": row.get("life_stage", ""),
    }


# ─────────────────────────────────────────────────────────
# Automated Format Checks
# ─────────────────────────────────────────────────────────

def run_format_checks(response: str) -> Dict:
    """Run automated format and compliance checks."""
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

    # 7. Response length (100-800 words)
    word_count = len(response.split())
    checks["response_length"] = {
        "passed": 100 <= word_count <= 800,
        "detail": f"{word_count} words",
    }

    # 8. No product link mentions
    has_product_link = "my3ionetra.com" in response.lower()
    checks["no_product_link"] = {
        "passed": not has_product_link,
        "detail": f"Product link {'present' if has_product_link else 'absent'}",
    }

    return checks


# ─────────────────────────────────────────────────────────
# Content Match Evaluation
# ─────────────────────────────────────────────────────────

def check_gita_match(response: str, expected_ref: str) -> Dict:
    """
    Check if the response references the expected Bhagavad Gita verse.
    Accepts exact match or same chapter.
    """
    if not expected_ref or not expected_ref.strip():
        return {"matched": False, "level": "no_expected", "detail": "No expected reference"}

    resp_lower = response.lower()
    ref = expected_ref.strip()

    # Parse expected: "BG 6.29" -> chapter=6, verse=29
    bg_match = re.match(r"BG\s+(\d+)\.(\d+)", ref)
    if not bg_match:
        return {"matched": False, "level": "unparseable", "detail": f"Cannot parse {ref}"}

    chapter = bg_match.group(1)
    verse = bg_match.group(2)

    # Exact match: "BG 6.29" or "6.29" or "chapter 6, verse 29"
    exact_patterns = [
        rf"bg\s*{chapter}\.{verse}",
        rf"bhagavad\s*gita\s*{chapter}\.{verse}",
        rf"gita\s*{chapter}\.{verse}",
        rf"chapter\s*{chapter}[,\s]+verse\s*{verse}",
        rf"{chapter}\.{verse}",
    ]
    for pat in exact_patterns:
        if re.search(pat, resp_lower):
            return {"matched": True, "level": "exact", "detail": f"Exact match: {ref}"}

    # Chapter match: same chapter, different verse
    chapter_patterns = [
        rf"bg\s*{chapter}\.\d+",
        rf"bhagavad\s*gita\s*{chapter}\.\d+",
        rf"gita\s*{chapter}\.\d+",
        rf"chapter\s*{chapter}",
    ]
    for pat in chapter_patterns:
        if re.search(pat, resp_lower):
            return {"matched": True, "level": "chapter", "detail": f"Same chapter ({chapter}), different verse"}

    # Any BG reference at all
    if re.search(r"(bhagavad\s*gita|gita\s+\d|bg\s+\d)", resp_lower):
        return {"matched": False, "level": "different", "detail": "Cites different BG verse"}

    return {"matched": False, "level": "none", "detail": "No Gita reference found"}


def check_mantra_match(response: str, expected_mantra: str) -> Dict:
    """Check if the response mentions the expected mantra."""
    if not expected_mantra or not expected_mantra.strip():
        return {"matched": False, "level": "no_expected", "detail": "No expected mantra"}

    resp_lower = response.lower()
    mantra_lower = expected_mantra.strip().lower()

    # Exact mantra match
    if mantra_lower in resp_lower:
        return {"matched": True, "level": "exact", "detail": f"Exact: {expected_mantra}"}

    # Partial match: key words from mantra name
    mantra_words = [w for w in mantra_lower.split() if len(w) > 2 and w != "om"]
    if mantra_words:
        matches = sum(1 for w in mantra_words if w in resp_lower)
        if matches >= len(mantra_words) * 0.5:
            return {"matched": True, "level": "partial", "detail": f"Partial match ({matches}/{len(mantra_words)} keywords)"}

    # Any mantra mentioned at all
    common_mantras = [
        "om namah shivaya", "gayatri", "mahamrityunjaya", "om shanti",
        "hare krishna", "om namo narayanaya", "hanuman chalisa",
        "om gan ganapataye", "maha lakshmi", "durga",
    ]
    mentioned = [m for m in common_mantras if m in resp_lower]
    if mentioned:
        return {"matched": False, "level": "alternative", "detail": f"Alternative mantra: {mentioned[0]}"}

    return {"matched": False, "level": "none", "detail": "No mantra mentioned"}


def check_practice_match(response: str, expected_practice: str) -> Dict:
    """Check if the response recommends the expected practice type."""
    if not expected_practice or not expected_practice.strip():
        return {"matched": False, "level": "no_expected", "detail": "No expected practice"}

    resp_lower = response.lower()
    practice_lower = expected_practice.strip().lower()

    # Direct match
    if practice_lower in resp_lower:
        return {"matched": True, "level": "exact", "detail": f"Exact: {expected_practice}"}

    # Practice synonyms
    practice_synonyms = {
        "self reflection": ["self-reflection", "introspect", "reflect", "contemplat", "atma-vichara", "atma vichara"],
        "pranayama": ["breathing", "breath work", "breathwork", "nadi shodhana", "anulom vilom", "pranayam"],
        "scripture reading": ["scripture", "reading", "svadhyaya", "study", "gita", "upanishad"],
        "meditation": ["meditat", "dhyana", "mindful", "sit quietly", "still the mind"],
        "japa": ["japa", "chanting", "mantra repetition", "mala", "108 times"],
        "yoga": ["yoga", "asana", "surya namaskar", "sun salutation"],
        "seva": ["seva", "service", "volunteer", "help others", "selfless"],
        "prayer": ["prayer", "prarthana", "puja", "worship", "aarti"],
        "fasting": ["fast", "upvas", "vrat", "ekadashi"],
        "gratitude": ["gratitude", "thankful", "grateful", "appreciation"],
        "journaling": ["journal", "writing", "diary", "write down"],
        "counseling": ["counsel", "therapist", "professional help", "talk to someone"],
    }

    # Check practice and its synonyms
    for practice_key, synonyms in practice_synonyms.items():
        if practice_lower in practice_key or practice_key in practice_lower:
            for syn in synonyms:
                if syn in resp_lower:
                    return {"matched": True, "level": "synonym", "detail": f"Synonym match: {syn}"}

    # Fallback: check all synonym lists
    for practice_key, synonyms in practice_synonyms.items():
        for syn in synonyms:
            if syn in resp_lower:
                return {"matched": False, "level": "alternative", "detail": f"Alternative practice: {practice_key}"}

    return {"matched": False, "level": "none", "detail": "No practice mentioned"}


def run_content_checks(response: str, row: Dict) -> Dict:
    """Run all content match evaluations."""
    return {
        "gita_match": check_gita_match(response, row.get("gita_reference", "")),
        "mantra_match": check_mantra_match(response, row.get("recommended_mantra", "")),
        "practice_match": check_practice_match(response, row.get("recommended_practice", "")),
    }


# ─────────────────────────────────────────────────────────
# LLM-as-Judge Evaluation
# ─────────────────────────────────────────────────────────

JUDGE_PROMPT = """You are an expert evaluator for a spiritual companion AI chatbot (3ioNetra — Mitra) rooted in Sanatana Dharma.

Score the bot's RESPONSE to the user's question on these 5 dimensions (1-5 scale each):

1. **demographic_appropriateness** (1-5): Is the response suitable for this user's age ({user_age}), gender ({user_gender}), and life stage ({life_stage})?
   - 1: Completely inappropriate for the demographic (e.g., complex philosophy for a teen)
   - 3: Mostly appropriate but some misalignment
   - 5: Perfectly calibrated for this specific user profile

2. **emotional_attunement** (1-5): Does it match the user's emotional tone ({emotional_tone})?
   - 1: Completely misreads the emotion (e.g., dismissive of anxiety)
   - 3: Acknowledges emotion but doesn't fully attune
   - 5: Deeply attuned — meets the user exactly where they are

3. **dharmic_integration** (1-5): Does it naturally weave in dharmic wisdom?
   - 1: No dharmic content or forced/preachy
   - 3: Dharmic content present but feels mechanical
   - 5: Dharmic wisdom woven in beautifully and naturally

4. **practice_specificity** (1-5): Are suggestions concrete and actionable?
   - 1: No practical guidance, only platitudes
   - 3: Some suggestions but vague
   - 5: Specific, concrete, doable steps

5. **overall_quality** (1-5): Holistic quality as a spiritual companion response.
   - 1: Would harm trust or be unhelpful
   - 3: Acceptable but unremarkable
   - 5: Exceptional — would genuinely help and connect

USER'S QUESTION:
{question}

USER PROFILE: {user_gender}, age {user_age}, {life_stage}
EMOTIONAL TONE: {emotional_tone}
PROBLEM CATEGORY: {problem_category}

EXPECTED GITA REFERENCE: {gita_reference}
EXPECTED MANTRA: {recommended_mantra}
EXPECTED PRACTICE: {recommended_practice}

BOT'S RESPONSE:
{response}

Respond with ONLY a valid JSON object (no markdown, no code fences):
{{"demographic_appropriateness": <1-5>, "emotional_attunement": <1-5>, "dharmic_integration": <1-5>, "practice_specificity": <1-5>, "overall_quality": <1-5>, "notes": "<brief 1-2 sentence evaluation note>"}}"""


def judge_response(genai_client, question: str, response: str, row: Dict) -> Dict:
    """Use Gemini Flash as judge to score the response."""
    prompt = JUDGE_PROMPT.format(
        user_age=row.get("user_age", ""),
        user_gender=row.get("user_gender", ""),
        life_stage=row.get("life_stage", ""),
        emotional_tone=row.get("emotional_tone", ""),
        problem_category=row.get("problem_category", ""),
        gita_reference=row.get("gita_reference", ""),
        recommended_mantra=row.get("recommended_mantra", ""),
        recommended_practice=row.get("recommended_practice", ""),
        question=question,
        response=response,
    )

    try:
        result = genai_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config={"temperature": 0.1},
        )
        text = result.text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        scores = json.loads(text)
        return scores
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"Judge parse error: {e}")
        return {
            "demographic_appropriateness": 0,
            "emotional_attunement": 0,
            "dharmic_integration": 0,
            "practice_specificity": 0,
            "overall_quality": 0,
            "notes": f"Judge error: {str(e)[:100]}",
        }


# ─────────────────────────────────────────────────────────
# Report Generator
# ─────────────────────────────────────────────────────────

def generate_report(results: List[Dict], output_path: str) -> str:
    """Generate the markdown performance report."""
    total = len(results)
    if total == 0:
        return ""

    score_keys = [
        "demographic_appropriateness", "emotional_attunement",
        "dharmic_integration", "practice_specificity", "overall_quality",
    ]

    # Overall means
    overall_means = {}
    for key in score_keys:
        vals = [r["judge_scores"].get(key, 0) for r in results if r["judge_scores"].get(key, 0) > 0]
        overall_means[key] = sum(vals) / len(vals) if vals else 0.0

    # Per-category breakdown
    by_category: Dict[str, List[Dict]] = defaultdict(list)
    for r in results:
        by_category[r["problem_category"]].append(r)

    cat_means = {}
    for cat, cat_results in sorted(by_category.items()):
        cat_means[cat] = {"count": len(cat_results)}
        for key in score_keys:
            vals = [r["judge_scores"].get(key, 0) for r in cat_results if r["judge_scores"].get(key, 0) > 0]
            cat_means[cat][key] = sum(vals) / len(vals) if vals else 0.0

    # Per-age-group breakdown
    by_age: Dict[str, List[Dict]] = defaultdict(list)
    for r in results:
        by_age[r["user_age"]].append(r)

    age_means = {}
    for age, age_results in sorted(by_age.items()):
        age_means[age] = {"count": len(age_results)}
        for key in score_keys:
            vals = [r["judge_scores"].get(key, 0) for r in age_results if r["judge_scores"].get(key, 0) > 0]
            age_means[age][key] = sum(vals) / len(vals) if vals else 0.0

    # Format compliance
    format_check_names = [
        "no_bullet_points", "no_numbered_lists", "no_markdown_headers",
        "no_hollow_phrases", "no_formulaic_endings", "verse_tag_compliance",
        "response_length", "no_product_link",
    ]
    format_pass_rates = {}
    for check_name in format_check_names:
        passed = sum(1 for r in results if r["format_checks"].get(check_name, {}).get("passed", False))
        format_pass_rates[check_name] = passed / total * 100

    # Content match rates
    content_keys = ["gita_match", "mantra_match", "practice_match"]
    content_rates = {}
    for ck in content_keys:
        matched = sum(1 for r in results if r["content_checks"].get(ck, {}).get("matched", False))
        content_rates[ck] = matched / total * 100

    # Level distributions for content matches
    content_levels = {}
    for ck in content_keys:
        levels: Dict[str, int] = defaultdict(int)
        for r in results:
            level = r["content_checks"].get(ck, {}).get("level", "unknown")
            levels[level] += 1
        content_levels[ck] = dict(levels)

    # Top 5 / Bottom 5
    scored = [r for r in results if r["judge_scores"].get("overall_quality", 0) > 0]
    sorted_by_quality = sorted(scored, key=lambda r: r["judge_scores"]["overall_quality"], reverse=True)
    top_5 = sorted_by_quality[:5]
    bottom_5 = sorted_by_quality[-5:]

    # Build report
    lines = []
    lines.append("# 3ioNetra — CSV Dataset Evaluation Report")
    lines.append(f"\n**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Model**: {settings.GEMINI_MODEL}")
    lines.append(f"**Sample Size**: {total} (from 50,000 dataset)")
    lines.append(f"**Categories**: {len(by_category)}")
    lines.append(f"**Age Groups**: {len(by_age)}")

    # Overall Scores
    lines.append("\n## Overall Judge Scores (Mean)")
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
        lines.append(f"| {label} | {format_pass_rates[check_name]:.1f}% |")

    # Content Match Rates
    lines.append("\n## Content Match Rates (vs Expected)")
    lines.append("")
    lines.append("| Content Type | Match Rate | Level Breakdown |")
    lines.append("|-------------|------------|-----------------|")
    for ck in content_keys:
        label = ck.replace("_", " ").title()
        levels = content_levels[ck]
        level_str = ", ".join(f"{k}: {v}" for k, v in sorted(levels.items()))
        lines.append(f"| {label} | {content_rates[ck]:.1f}% | {level_str} |")

    # Per-Category Breakdown
    lines.append("\n## Per-Category Performance")
    lines.append("")
    lines.append("| Category | N | Demo | Emo | Dharmic | Practice | Overall |")
    lines.append("|----------|---|------|-----|---------|----------|---------|")
    for cat in sorted(cat_means.keys()):
        m = cat_means[cat]
        lines.append(
            f"| {cat} | {m['count']} | {m['demographic_appropriateness']:.1f} "
            f"| {m['emotional_attunement']:.1f} | {m['dharmic_integration']:.1f} "
            f"| {m['practice_specificity']:.1f} | {m['overall_quality']:.1f} |"
        )

    # Per-Age-Group Breakdown
    lines.append("\n## Per-Age-Group Performance")
    lines.append("")
    lines.append("| Age Group | N | Demo | Emo | Dharmic | Practice | Overall |")
    lines.append("|-----------|---|------|-----|---------|----------|---------|")
    for age in sorted(age_means.keys()):
        m = age_means[age]
        lines.append(
            f"| {age} | {m['count']} | {m['demographic_appropriateness']:.1f} "
            f"| {m['emotional_attunement']:.1f} | {m['dharmic_integration']:.1f} "
            f"| {m['practice_specificity']:.1f} | {m['overall_quality']:.1f} |"
        )

    # Top 5 Best
    lines.append("\n## Top 5 Best Responses")
    for i, r in enumerate(top_5, 1):
        lines.append(f"\n### {i}. Row {r['_row_id']} — {r['problem_category']} ({r['emotional_tone']})")
        lines.append(f"- **Score**: {r['judge_scores']['overall_quality']}/5")
        lines.append(f"- **User**: {r['user_gender']}, {r['user_age']}, {r['life_stage']}")
        lines.append(f"- **Question**: {r['user_question'][:100]}...")
        lines.append(f"- **Judge Notes**: {r['judge_scores'].get('notes', 'N/A')}")

    # Bottom 5 Worst
    lines.append("\n## Bottom 5 Responses (Need Improvement)")
    for i, r in enumerate(bottom_5, 1):
        lines.append(f"\n### {i}. Row {r['_row_id']} — {r['problem_category']} ({r['emotional_tone']})")
        lines.append(f"- **Score**: {r['judge_scores']['overall_quality']}/5")
        lines.append(f"- **User**: {r['user_gender']}, {r['user_age']}, {r['life_stage']}")
        lines.append(f"- **Question**: {r['user_question'][:100]}...")
        lines.append(f"- **Judge Notes**: {r['judge_scores'].get('notes', 'N/A')}")

    # Response Length Stats
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
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Load CSV
    if not os.path.exists(CSV_PATH):
        logger.error(f"CSV dataset not found at {CSV_PATH}")
        sys.exit(1)

    all_rows = load_csv(CSV_PATH)

    # Load or generate sample
    if os.path.exists(SAMPLE_FILE):
        with open(SAMPLE_FILE, "r") as f:
            sample_ids = json.load(f)
        # Reconstruct sample from saved IDs
        id_set = set(sample_ids)
        sample = [r for r in all_rows if r["_row_id"] in id_set]
        logger.info(f"Loaded existing sample of {len(sample)} rows from {SAMPLE_FILE}")
    else:
        sample = stratified_sample(all_rows, SAMPLE_SIZE)
        sample_ids = [r["_row_id"] for r in sample]
        with open(SAMPLE_FILE, "w") as f:
            json.dump(sample_ids, f)
        logger.info(f"Saved new sample IDs to {SAMPLE_FILE}")

    # Initialize Gemini
    if not settings.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not set in .env")
        sys.exit(1)

    from google import genai
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    # Load system instruction
    prompt_dir = os.path.join(BACKEND_DIR, "prompts")
    pm = PromptManager(prompt_dir)
    system_instruction = pm.get_prompt("spiritual_mitra", "system_instruction")
    if not system_instruction:
        logger.error("Could not load system_instruction from spiritual_mitra.yaml")
        sys.exit(1)
    logger.info(f"System instruction loaded ({len(system_instruction)} chars)")
    logger.info(f"Model: {settings.GEMINI_MODEL}")

    def get_phase_instructions(phase: ConversationPhase) -> str:
        return pm.get_prompt("spiritual_mitra", f"phase_prompts.{phase.value}", default="")

    def generate_response_sync(query: str, user_profile: Dict, emotional_tone: str, problem_category: str) -> str:
        """Generate a single response using Gemini directly."""
        profile_parts = []
        if user_profile.get("age_group"):
            profile_parts.append(f"   - Age group: {user_profile['age_group']}")
        if user_profile.get("gender"):
            profile_parts.append(f"   - Gender: {user_profile['gender']}")
        if user_profile.get("profession"):
            profile_parts.append(f"   - Profession: {user_profile['profession']}")
        if user_profile.get("life_stage"):
            profile_parts.append(f"   - Life stage: {user_profile['life_stage']}")

        profile_text = ""
        if profile_parts:
            profile_text = "\n" + "=" * 60 + "\nWHO YOU ARE SPEAKING TO:\n" + "=" * 60 + "\n"
            profile_text += "\n".join(profile_parts) + "\n" + "=" * 60 + "\n"

        phase = ConversationPhase.GUIDANCE
        phase_instructions = get_phase_instructions(phase)

        prompt = f"""{profile_text}

EMOTIONAL CONTEXT: The user feels {emotional_tone.lower()} about {problem_category.lower()}.

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

    # Load existing responses for resumability
    existing_responses = {}
    if os.path.exists(RESPONSES_FILE):
        with open(RESPONSES_FILE, "r", encoding="utf-8") as f:
            existing_responses = json.load(f)
        logger.info(f"Loaded {len(existing_responses)} existing responses (resuming)")

    # ── Phase 1: Generate Responses ──
    logger.info("=" * 60)
    logger.info("PHASE 1: Generating bot responses")
    logger.info("=" * 60)

    responses = dict(existing_responses)

    for i, row in enumerate(sample):
        rid = row["_row_id"]

        if rid in responses:
            logger.info(f"[{i+1}/{len(sample)}] Row {rid} — cached, skipping")
            continue

        question = row.get("user_question", "")
        user_profile = build_user_profile(row)
        emotional_tone = row.get("emotional_tone", "")
        problem_category = row.get("problem_category", "")

        logger.info(f"[{i+1}/{len(sample)}] Row {rid} — {problem_category} / {emotional_tone} / {row.get('user_age', '')}")

        try:
            response_text = generate_response_sync(
                query=question,
                user_profile=user_profile,
                emotional_tone=emotional_tone,
                problem_category=problem_category,
            )
        except Exception as e:
            logger.error(f"  Error generating response for Row {rid}: {e}")
            response_text = f"[ERROR] {str(e)[:200]}"

        responses[rid] = response_text

        with open(RESPONSES_FILE, "w", encoding="utf-8") as f:
            json.dump(responses, f, ensure_ascii=False, indent=2)

        time.sleep(DELAY_BETWEEN_CALLS)

    logger.info(f"Phase 1 complete: {len(responses)} responses generated")

    # ── Phase 2: Format Checks + Content Match ──
    logger.info("=" * 60)
    logger.info("PHASE 2: Format checks & content matching")
    logger.info("=" * 60)

    results = []
    for row in sample:
        rid = row["_row_id"]
        bot_response = responses.get(rid, "")

        format_checks = run_format_checks(bot_response)
        content_checks = run_content_checks(bot_response, row)

        results.append({
            "_row_id": rid,
            "user_gender": row.get("user_gender", ""),
            "user_age": row.get("user_age", ""),
            "life_stage": row.get("life_stage", ""),
            "problem_category": row.get("problem_category", ""),
            "emotional_tone": row.get("emotional_tone", ""),
            "user_question": row.get("user_question", ""),
            "gita_reference": row.get("gita_reference", ""),
            "recommended_mantra": row.get("recommended_mantra", ""),
            "recommended_practice": row.get("recommended_practice", ""),
            "bot_response": bot_response,
            "format_checks": format_checks,
            "content_checks": content_checks,
            "judge_scores": {},
        })

    logger.info(f"Phase 2 complete: {len(results)} responses checked")

    # ── Phase 3: LLM-as-Judge ──
    logger.info("=" * 60)
    logger.info("PHASE 3: LLM-as-Judge evaluation")
    logger.info("=" * 60)

    existing_judges = {}
    if os.path.exists(JUDGE_SCORES_FILE):
        with open(JUDGE_SCORES_FILE, "r", encoding="utf-8") as f:
            existing_judges = json.load(f)
        logger.info(f"Loaded {len(existing_judges)} existing judge scores (resuming)")

    for i, r in enumerate(results):
        rid = r["_row_id"]

        if rid in existing_judges:
            r["judge_scores"] = existing_judges[rid]
            logger.info(f"[{i+1}/{len(results)}] Row {rid} — judge cached, skipping")
            continue

        if r["bot_response"].startswith("[ERROR]"):
            r["judge_scores"] = {
                "demographic_appropriateness": 0, "emotional_attunement": 0,
                "dharmic_integration": 0, "practice_specificity": 0,
                "overall_quality": 0, "notes": "Response generation failed",
            }
            existing_judges[rid] = r["judge_scores"]
            continue

        logger.info(f"[{i+1}/{len(results)}] Row {rid} — judging...")

        scores = judge_response(client, r["user_question"], r["bot_response"], r)
        r["judge_scores"] = scores
        existing_judges[rid] = scores

        with open(JUDGE_SCORES_FILE, "w", encoding="utf-8") as f:
            json.dump(existing_judges, f, ensure_ascii=False, indent=2)

        time.sleep(JUDGE_DELAY)

    logger.info(f"Phase 3 complete: judge scores for {len(results)} responses")

    # ── Phase 4: Save Detailed CSV ──
    logger.info("=" * 60)
    logger.info("PHASE 4: Saving detailed results CSV")
    logger.info("=" * 60)

    csv_fields = [
        "_row_id", "user_gender", "user_age", "life_stage",
        "problem_category", "emotional_tone", "user_question",
        "gita_reference", "recommended_mantra", "recommended_practice",
        "bot_response", "word_count",
        "fmt_no_bullets", "fmt_no_numbers", "fmt_no_headers",
        "fmt_no_hollow", "fmt_no_formulaic", "fmt_verse_ok", "fmt_length_ok",
        "fmt_no_product_link",
        "match_gita", "match_gita_level", "match_mantra", "match_mantra_level",
        "match_practice", "match_practice_level",
        "judge_demo", "judge_emo", "judge_dharmic", "judge_practice", "judge_overall",
        "judge_notes",
    ]

    with open(DETAILED_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        for r in results:
            fc = r["format_checks"]
            cc = r["content_checks"]
            js = r["judge_scores"]
            writer.writerow({
                "_row_id": r["_row_id"],
                "user_gender": r["user_gender"],
                "user_age": r["user_age"],
                "life_stage": r["life_stage"],
                "problem_category": r["problem_category"],
                "emotional_tone": r["emotional_tone"],
                "user_question": r["user_question"],
                "gita_reference": r["gita_reference"],
                "recommended_mantra": r["recommended_mantra"],
                "recommended_practice": r["recommended_practice"],
                "bot_response": r["bot_response"][:500],
                "word_count": len(r["bot_response"].split()),
                "fmt_no_bullets": "PASS" if fc.get("no_bullet_points", {}).get("passed") else "FAIL",
                "fmt_no_numbers": "PASS" if fc.get("no_numbered_lists", {}).get("passed") else "FAIL",
                "fmt_no_headers": "PASS" if fc.get("no_markdown_headers", {}).get("passed") else "FAIL",
                "fmt_no_hollow": "PASS" if fc.get("no_hollow_phrases", {}).get("passed") else "FAIL",
                "fmt_no_formulaic": "PASS" if fc.get("no_formulaic_endings", {}).get("passed") else "FAIL",
                "fmt_verse_ok": "PASS" if fc.get("verse_tag_compliance", {}).get("passed") else "FAIL",
                "fmt_length_ok": "PASS" if fc.get("response_length", {}).get("passed") else "FAIL",
                "fmt_no_product_link": "PASS" if fc.get("no_product_link", {}).get("passed") else "FAIL",
                "match_gita": "YES" if cc.get("gita_match", {}).get("matched") else "NO",
                "match_gita_level": cc.get("gita_match", {}).get("level", ""),
                "match_mantra": "YES" if cc.get("mantra_match", {}).get("matched") else "NO",
                "match_mantra_level": cc.get("mantra_match", {}).get("level", ""),
                "match_practice": "YES" if cc.get("practice_match", {}).get("matched") else "NO",
                "match_practice_level": cc.get("practice_match", {}).get("level", ""),
                "judge_demo": js.get("demographic_appropriateness", 0),
                "judge_emo": js.get("emotional_attunement", 0),
                "judge_dharmic": js.get("dharmic_integration", 0),
                "judge_practice": js.get("practice_specificity", 0),
                "judge_overall": js.get("overall_quality", 0),
                "judge_notes": js.get("notes", ""),
            })

    logger.info(f"Detailed CSV saved to {DETAILED_CSV}")

    # ── Phase 5: Generate Report ──
    logger.info("=" * 60)
    logger.info("PHASE 5: Generating evaluation report")
    logger.info("=" * 60)

    report = generate_report(results, REPORT_FILE)

    elapsed = time.time() - start_time
    logger.info(f"\nEvaluation complete in {elapsed/60:.1f} minutes")
    logger.info(f"Results: {OUTPUT_DIR}")

    print("\n" + "=" * 70)
    print(report)
    print("=" * 70)


if __name__ == "__main__":
    main()
