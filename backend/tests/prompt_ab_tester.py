"""
3ioNetra Spiritual Companion — Prompt A/B Tester
=================================================
Compares two prompt YAML versions side-by-side on the same 20 built-in
scenarios.  Uses independent LLM-as-judge scoring (5 dimensions) plus a
head-to-head paired comparison to determine a winner.

Usage:
    cd backend/
    python tests/prompt_ab_tester.py --prompt-a spiritual_mitra --prompt-b spiritual_mitra_v5.3
    python tests/prompt_ab_tester.py --prompt-a spiritual_mitra --prompt-b spiritual_mitra_v5.3 --resume
    python tests/prompt_ab_tester.py --prompt-a spiritual_mitra --prompt-b spiritual_mitra_v5.3 --category grief
"""

import argparse
import json
import logging
import os
import random
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional

# ── Path setup ──────────────────────────────────────────
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from config import settings  # noqa: E402
from models.session import ConversationPhase  # noqa: E402
from services.prompt_manager import PromptManager  # noqa: E402
from tests.eval_utils import run_format_checks, call_llm_judge  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ab_test_results")
RESULTS_FILE = os.path.join(OUTPUT_DIR, "ab_results.json")
REPORT_FILE = os.path.join(OUTPUT_DIR, "ab_test_report.md")

DELAY_BETWEEN_CALLS = 2.0  # seconds between Gemini generation calls
JUDGE_DELAY = 1.0  # seconds between judge calls
JUDGE_MODEL = "gemini-2.0-flash"

SCORE_KEYS = [
    "tone_match", "dharmic_integration", "practice_specificity",
    "conversational_flow", "overall_quality",
]

H2H_KEYS = ["tone_winner", "dharmic_winner", "clarity_winner", "overall_winner"]


# ── Test Scenarios ──────────────────────────────────────

@dataclass
class TestScenario:
    id: int
    category: str
    question: str
    tone_guide: str
    dharmic_principle: str
    phase: ConversationPhase
    user_profile: Dict = field(default_factory=dict)


SCENARIOS: List[TestScenario] = [
    # Grief (1-2)
    TestScenario(
        id=1, category="grief",
        question="meri maa ka kal dehant ho gaya",
        tone_guide="Tender, spacious",
        dharmic_principle="Impermanence, atma's continuity",
        phase=ConversationPhase.LISTENING,
        user_profile={"age_group": "28-45"},
    ),
    TestScenario(
        id=2, category="grief",
        question="best friend ne suicide kar liya",
        tone_guide="Steady, safety-first",
        dharmic_principle="Compassion, helpline",
        phase=ConversationPhase.GUIDANCE,
        user_profile={"age_group": "22-28"},
    ),
    # Career (3-4)
    TestScenario(
        id=3, category="career",
        question="job mein growth nahi ho rahi, resign karu?",
        tone_guide="Affirming, practical",
        dharmic_principle="Svadharma, nishkama karma",
        phase=ConversationPhase.GUIDANCE,
        user_profile={"age_group": "24-30", "profession": "working professional"},
    ),
    TestScenario(
        id=4, category="career",
        question="business fail ho gaya, loan pe loan hai",
        tone_guide="Calm, anchoring",
        dharmic_principle="Detachment from outcomes",
        phase=ConversationPhase.LISTENING,
        user_profile={"age_group": "28-40", "profession": "entrepreneur"},
    ),
    # Family (5-6)
    TestScenario(
        id=5, category="family",
        question="pati se daily jhagda hota hai",
        tone_guide="Warm, non-judgmental",
        dharmic_principle="Grihastha dharma",
        phase=ConversationPhase.LISTENING,
        user_profile={"age_group": "28-45"},
    ),
    TestScenario(
        id=6, category="family",
        question="bete ne shaadi kar li bina bataye",
        tone_guide="Empathetic, wise",
        dharmic_principle="Letting go, dharmic love",
        phase=ConversationPhase.GUIDANCE,
        user_profile={"age_group": "45-60"},
    ),
    # Spiritual (7-8)
    TestScenario(
        id=7, category="spiritual",
        question="prayer karta hoon par kuch nahi hota",
        tone_guide="Gentle, patient",
        dharmic_principle="Shraddha, abhyasa",
        phase=ConversationPhase.GUIDANCE,
        user_profile={"age_group": "28-40"},
    ),
    TestScenario(
        id=8, category="spiritual",
        question="meditation mein mann nahi lagta",
        tone_guide="Encouraging",
        dharmic_principle="Abhyasa-vairagya",
        phase=ConversationPhase.GUIDANCE,
        user_profile={"age_group": "22-28"},
    ),
    # Anxiety (9-10)
    TestScenario(
        id=9, category="anxiety",
        question="raat ko neend nahi aati, thoughts aate rehte hain",
        tone_guide="Calming, anchoring",
        dharmic_principle="Pranayama, So Hum",
        phase=ConversationPhase.GUIDANCE,
        user_profile={"age_group": "24-30"},
    ),
    TestScenario(
        id=10, category="anxiety",
        question="exam ka bahut pressure hai",
        tone_guide="Supportive",
        dharmic_principle="Karma yoga (Gita 2.47)",
        phase=ConversationPhase.GUIDANCE,
        user_profile={"age_group": "16-20", "profession": "student"},
    ),
    # Anger (11-12)
    TestScenario(
        id=11, category="anger",
        question="boss ne publicly insult kiya",
        tone_guide="Firm, validating",
        dharmic_principle="Krodha management",
        phase=ConversationPhase.LISTENING,
        user_profile={"age_group": "24-30", "profession": "working professional"},
    ),
    TestScenario(
        id=12, category="anger",
        question="friend ne peeche se backstab kiya",
        tone_guide="Validating",
        dharmic_principle="Forgiveness, satsang",
        phase=ConversationPhase.GUIDANCE,
        user_profile={"age_group": "22-28"},
    ),
    # Self-worth (13-14)
    TestScenario(
        id=13, category="self-worth",
        question="main kisi kaam ka nahi hoon",
        tone_guide="Warm, affirming",
        dharmic_principle="Atma-garima",
        phase=ConversationPhase.LISTENING,
        user_profile={"age_group": "22-28"},
    ),
    TestScenario(
        id=14, category="self-worth",
        question="sab mere se aage nikal gaye",
        tone_guide="Understanding",
        dharmic_principle="Non-comparison, svadharma",
        phase=ConversationPhase.GUIDANCE,
        user_profile={"age_group": "24-30", "profession": "working professional"},
    ),
    # Health (15-16)
    TestScenario(
        id=15, category="health",
        question="cancer ka diagnosis aaya hai",
        tone_guide="Tender, steady",
        dharmic_principle="Maha Mrityunjaya",
        phase=ConversationPhase.LISTENING,
        user_profile={"age_group": "45-60"},
    ),
    TestScenario(
        id=16, category="health",
        question="diabetes se bahut thak gaya hoon",
        tone_guide="Supportive",
        dharmic_principle="Dhanvantari, acceptance",
        phase=ConversationPhase.GUIDANCE,
        user_profile={"age_group": "40-55"},
    ),
    # Panchang (17-18)
    TestScenario(
        id=17, category="panchang",
        question="aaj ka tithi kya hai?",
        tone_guide="Informative, warm",
        dharmic_principle="Panchang awareness",
        phase=ConversationPhase.GUIDANCE,
        user_profile={},
    ),
    TestScenario(
        id=18, category="panchang",
        question="kab shuru karu naya vrat?",
        tone_guide="Helpful, precise",
        dharmic_principle="Muhurat, tithi",
        phase=ConversationPhase.GUIDANCE,
        user_profile={},
    ),
    # Relationships (19)
    TestScenario(
        id=19, category="relationships",
        question="breakup ke baad empty feel ho raha hai",
        tone_guide="Compassionate",
        dharmic_principle="Atma-garima, self-love",
        phase=ConversationPhase.LISTENING,
        user_profile={"age_group": "22-28"},
    ),
    # Closure (20)
    TestScenario(
        id=20, category="closure",
        question="thank you mitra, bahut accha laga baat karke",
        tone_guide="Warm, brief",
        dharmic_principle="Blessing, continuity",
        phase=ConversationPhase.CLOSURE,
        user_profile={},
    ),
]


# ── Judge Prompts ───────────────────────────────────────

INDEPENDENT_JUDGE_PROMPT = """You are an expert evaluator for a spiritual companion AI chatbot (3ioNetra — Mitra) rooted in Sanatana Dharma.

Score the bot's RESPONSE to the user's question on these 5 dimensions (1-5 scale each):

1. **tone_match** (1-5): Does the response tone match the expected tone? Expected tone: "{tone_guide}"
   - 1: Completely wrong tone  - 3: Partially matches  - 5: Perfect tone match

2. **dharmic_integration** (1-5): Does it naturally weave in the dharmic principle? Expected: "{dharmic_principle}"
   - 1: No dharmic content or forced/preachy  - 3: Present but mechanical  - 5: Woven in beautifully

3. **practice_specificity** (1-5): Are suggestions concrete and actionable?
   - 1: No practical guidance, only platitudes  - 3: Some suggestions but vague  - 5: Specific, doable steps

4. **conversational_flow** (1-5): Does it read like a warm, knowledgeable friend?
   - 1: Robotic, uses bullet points/headers  - 3: Mostly natural  - 5: Genuine conversation

5. **overall_quality** (1-5): Holistic quality as an ideal spiritual companion response.
   - 1: Would harm trust  - 3: Acceptable but unremarkable  - 5: Exceptional

USER'S QUESTION:
{question}

CONVERSATION PHASE: {phase}

BOT'S RESPONSE:
{response}

Respond with ONLY a valid JSON object (no markdown, no code fences):
{{"tone_match": <1-5>, "dharmic_integration": <1-5>, "practice_specificity": <1-5>, "conversational_flow": <1-5>, "overall_quality": <1-5>, "notes": "<brief 1-2 sentence evaluation note>"}}"""


H2H_JUDGE_PROMPT = """You are an expert evaluator comparing two responses from a spiritual companion AI chatbot (3ioNetra — Mitra) rooted in Sanatana Dharma.

The user asked: "{question}"
Expected tone: "{tone_guide}"
Expected dharmic principle: "{dharmic_principle}"
Conversation phase: {phase}

--- Response 1 ---
{response_1}

--- Response 2 ---
{response_2}

Compare both responses and pick a winner on each dimension. Use "1" if Response 1 is better, "2" if Response 2 is better, or "tie" if they are equivalent.

Dimensions:
- tone_winner: Which response better matches the expected tone?
- dharmic_winner: Which response integrates dharmic wisdom more naturally?
- clarity_winner: Which response is clearer, more specific, and more conversational?
- overall_winner: Which response is better overall as a spiritual companion?

Respond with ONLY a valid JSON object (no markdown, no code fences):
{{"tone_winner": "<1 or 2 or tie>", "dharmic_winner": "<1 or 2 or tie>", "clarity_winner": "<1 or 2 or tie>", "overall_winner": "<1 or 2 or tie>", "reasoning": "<brief 1-2 sentence explanation>"}}"""


# ── Response Generation ─────────────────────────────────

def generate_response_for_prompt(
    client,
    system_instruction: str,
    phase_prompt: str,
    scenario: TestScenario,
) -> str:
    """Generate a single response using Gemini with the given prompt config."""
    profile_text = ""
    if scenario.user_profile:
        parts = []
        if scenario.user_profile.get("age_group"):
            parts.append(f"   - Age group: {scenario.user_profile['age_group']}")
        if scenario.user_profile.get("profession"):
            parts.append(f"   - Profession: {scenario.user_profile['profession']}")
        if parts:
            profile_text = (
                "\n" + "=" * 60
                + "\nWHO YOU ARE SPEAKING TO:\n"
                + "=" * 60 + "\n"
                + "\n".join(parts) + "\n"
                + "=" * 60 + "\n"
            )

    prompt = f"""{profile_text}

User's message:
{scenario.question}

{'=' * 60}
YOUR INSTRUCTIONS FOR THIS PHASE ({scenario.phase.value}):
{'=' * 60}
{phase_prompt}

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


# ── Head-to-Head Judge ──────────────────────────────────

def judge_head_to_head(
    client,
    scenario: TestScenario,
    response_a: str,
    response_b: str,
) -> Dict:
    """
    Run a paired comparison. Randomises order to eliminate position bias.
    Returns dict with winners mapped back to A/B (not 1/2).
    """
    # Randomise which response appears first
    a_first = random.choice([True, False])
    if a_first:
        r1, r2 = response_a, response_b
    else:
        r1, r2 = response_b, response_a

    prompt = H2H_JUDGE_PROMPT.format(
        question=scenario.question,
        tone_guide=scenario.tone_guide,
        dharmic_principle=scenario.dharmic_principle,
        phase=scenario.phase.value,
        response_1=r1,
        response_2=r2,
    )

    raw = call_llm_judge(client, prompt, H2H_KEYS)

    # Map "1"/"2"/"tie" back to "A"/"B"/"tie"
    def map_winner(val: str) -> str:
        val = str(val).strip().lower()
        if val == "tie":
            return "tie"
        if val == "1":
            return "A" if a_first else "B"
        if val == "2":
            return "B" if a_first else "A"
        return "tie"  # fallback

    result = {}
    for key in H2H_KEYS:
        result[key] = map_winner(raw.get(key, "tie"))
    result["reasoning"] = raw.get("reasoning", "")
    result["position_order"] = "A_first" if a_first else "B_first"
    return result


# ── Main Pipeline ───────────────────────────────────────

def run_ab_test(
    prompt_a_name: str,
    prompt_b_name: str,
    resume: bool = False,
    category_filter: Optional[str] = None,
):
    """Run the full A/B test pipeline."""
    start_time = time.time()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ── Validate Gemini key ──
    if not settings.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not set in .env")
        sys.exit(1)

    from google import genai
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    # ── Load prompts ──
    prompt_dir = os.path.join(BACKEND_DIR, "prompts")
    pm = PromptManager(prompt_dir)

    sys_a = pm.get_prompt(prompt_a_name, "system_instruction")
    sys_b = pm.get_prompt(prompt_b_name, "system_instruction")

    if not sys_a:
        logger.error(f"Could not load system_instruction from {prompt_a_name}.yaml")
        sys.exit(1)
    if not sys_b:
        logger.error(f"Could not load system_instruction from {prompt_b_name}.yaml")
        sys.exit(1)

    logger.info(f"Prompt A: {prompt_a_name} ({len(sys_a)} chars)")
    logger.info(f"Prompt B: {prompt_b_name} ({len(sys_b)} chars)")

    # ── Filter scenarios ──
    scenarios = SCENARIOS
    if category_filter:
        scenarios = [s for s in SCENARIOS if s.category == category_filter.lower()]
        if not scenarios:
            logger.error(f"No scenarios found for category '{category_filter}'")
            sys.exit(1)
    logger.info(f"Scenarios: {len(scenarios)}")

    # ── Load cached results for resumability ──
    cached: Dict = {}
    if resume and os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            cached = json.load(f)
        logger.info(f"Resuming: loaded {len(cached.get('scenarios', {}))} cached scenario results")

    results_by_id: Dict[str, Dict] = cached.get("scenarios", {})

    # ── Process each scenario ──
    for i, scenario in enumerate(scenarios):
        sid = str(scenario.id)

        if sid in results_by_id and results_by_id[sid].get("h2h_verdict"):
            logger.info(f"[{i+1}/{len(scenarios)}] Scenario {sid} — cached, skipping")
            continue

        logger.info(f"[{i+1}/{len(scenarios)}] Scenario {sid} — {scenario.category}: {scenario.question[:50]}...")

        entry = results_by_id.get(sid, {
            "id": scenario.id,
            "category": scenario.category,
            "question": scenario.question,
            "tone_guide": scenario.tone_guide,
            "dharmic_principle": scenario.dharmic_principle,
            "phase": scenario.phase.value,
        })

        # Get phase prompts
        phase_prompt_a = pm.get_prompt(prompt_a_name, f"phase_prompts.{scenario.phase.value}", default="")
        phase_prompt_b = pm.get_prompt(prompt_b_name, f"phase_prompts.{scenario.phase.value}", default="")

        # ── Step A: Generate response with prompt A ──
        if not entry.get("response_a"):
            logger.info(f"  Generating response A ({prompt_a_name})...")
            try:
                entry["response_a"] = generate_response_for_prompt(
                    client, sys_a, phase_prompt_a, scenario,
                )
            except Exception as e:
                logger.error(f"  Error generating A: {e}")
                entry["response_a"] = f"[ERROR] {str(e)[:200]}"
            time.sleep(DELAY_BETWEEN_CALLS)

        # ── Step B: Generate response with prompt B ──
        if not entry.get("response_b"):
            logger.info(f"  Generating response B ({prompt_b_name})...")
            try:
                entry["response_b"] = generate_response_for_prompt(
                    client, sys_b, phase_prompt_b, scenario,
                )
            except Exception as e:
                logger.error(f"  Error generating B: {e}")
                entry["response_b"] = f"[ERROR] {str(e)[:200]}"
            time.sleep(DELAY_BETWEEN_CALLS)

        # ── Step C: Format checks ──
        entry["format_checks_a"] = run_format_checks(entry["response_a"])
        entry["format_checks_b"] = run_format_checks(entry["response_b"])

        # ── Step D: Independent judge on A ──
        if not entry.get("scores_a"):
            logger.info("  Judging response A...")
            prompt = INDEPENDENT_JUDGE_PROMPT.format(
                tone_guide=scenario.tone_guide,
                dharmic_principle=scenario.dharmic_principle,
                question=scenario.question,
                phase=scenario.phase.value,
                response=entry["response_a"],
            )
            entry["scores_a"] = call_llm_judge(client, prompt, SCORE_KEYS)
            time.sleep(JUDGE_DELAY)

        # ── Step E: Independent judge on B ──
        if not entry.get("scores_b"):
            logger.info("  Judging response B...")
            prompt = INDEPENDENT_JUDGE_PROMPT.format(
                tone_guide=scenario.tone_guide,
                dharmic_principle=scenario.dharmic_principle,
                question=scenario.question,
                phase=scenario.phase.value,
                response=entry["response_b"],
            )
            entry["scores_b"] = call_llm_judge(client, prompt, SCORE_KEYS)
            time.sleep(JUDGE_DELAY)

        # ── Step F: Head-to-head comparison ──
        if not entry.get("h2h_verdict"):
            logger.info("  Running head-to-head comparison...")
            entry["h2h_verdict"] = judge_head_to_head(
                client, scenario, entry["response_a"], entry["response_b"],
            )
            time.sleep(JUDGE_DELAY)

        results_by_id[sid] = entry

        # Save progress incrementally
        _save_results(results_by_id, prompt_a_name, prompt_b_name)

    # ── Generate report ──
    logger.info("=" * 60)
    logger.info("Generating A/B test report")
    logger.info("=" * 60)

    report = generate_report(results_by_id, prompt_a_name, prompt_b_name)

    elapsed = time.time() - start_time
    logger.info(f"\nA/B test complete in {elapsed / 60:.1f} minutes")
    logger.info(f"Results: {OUTPUT_DIR}")

    print("\n" + "=" * 70)
    print(report)
    print("=" * 70)


def _save_results(results_by_id: Dict, prompt_a: str, prompt_b: str):
    """Save current results to JSON."""
    data = {
        "prompt_a": prompt_a,
        "prompt_b": prompt_b,
        "model": settings.GEMINI_MODEL,
        "judge_model": JUDGE_MODEL,
        "timestamp": datetime.now().isoformat(),
        "scenarios": results_by_id,
    }
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Report Generator ────────────────────────────────────

def generate_report(
    results_by_id: Dict[str, Dict],
    prompt_a_name: str,
    prompt_b_name: str,
) -> str:
    """Generate the markdown A/B test report."""
    results = list(results_by_id.values())
    total = len(results)
    if total == 0:
        return "No results to report."

    # ── Aggregate independent scores ──
    means_a, means_b = {}, {}
    for key in SCORE_KEYS:
        vals_a = [r["scores_a"].get(key, 0) for r in results if r.get("scores_a", {}).get(key, 0) > 0]
        vals_b = [r["scores_b"].get(key, 0) for r in results if r.get("scores_b", {}).get(key, 0) > 0]
        means_a[key] = sum(vals_a) / len(vals_a) if vals_a else 0.0
        means_b[key] = sum(vals_b) / len(vals_b) if vals_b else 0.0

    composite_a = sum(means_a.values()) / len(means_a) if means_a else 0
    composite_b = sum(means_b.values()) / len(means_b) if means_b else 0

    # ── Aggregate head-to-head wins ──
    h2h_counts = {}
    for key in H2H_KEYS:
        a_wins = sum(1 for r in results if r.get("h2h_verdict", {}).get(key) == "A")
        b_wins = sum(1 for r in results if r.get("h2h_verdict", {}).get(key) == "B")
        ties = total - a_wins - b_wins
        h2h_counts[key] = {"A": a_wins, "B": b_wins, "tie": ties}

    overall_h2h = h2h_counts.get("overall_winner", {"A": 0, "B": 0, "tie": 0})

    # ── Per-category breakdown ──
    categories: Dict[str, List[Dict]] = {}
    for r in results:
        cat = r.get("category", "unknown")
        categories.setdefault(cat, []).append(r)

    cat_summary = {}
    for cat, cat_results in sorted(categories.items()):
        a_avg = 0.0
        b_avg = 0.0
        count = len(cat_results)
        for r in cat_results:
            a_avg += r.get("scores_a", {}).get("overall_quality", 0)
            b_avg += r.get("scores_b", {}).get("overall_quality", 0)
        a_avg /= count
        b_avg /= count
        cat_h2h_a = sum(1 for r in cat_results if r.get("h2h_verdict", {}).get("overall_winner") == "A")
        cat_h2h_b = sum(1 for r in cat_results if r.get("h2h_verdict", {}).get("overall_winner") == "B")
        cat_summary[cat] = {
            "count": count, "a_avg": a_avg, "b_avg": b_avg,
            "h2h_a": cat_h2h_a, "h2h_b": cat_h2h_b,
        }

    # ── Format compliance ──
    format_checks_list = [
        "no_bullet_points", "no_numbered_lists", "no_markdown_headers",
        "no_hollow_phrases", "no_formulaic_endings", "verse_tag_compliance",
        "response_length",
    ]
    fmt_a, fmt_b = {}, {}
    for check in format_checks_list:
        fmt_a[check] = sum(
            1 for r in results
            if r.get("format_checks_a", {}).get(check, {}).get("passed", False)
        ) / total * 100
        fmt_b[check] = sum(
            1 for r in results
            if r.get("format_checks_b", {}).get(check, {}).get("passed", False)
        ) / total * 100

    # ── Biggest wins (by score delta) ──
    deltas = []
    for r in results:
        oa = r.get("scores_a", {}).get("overall_quality", 0)
        ob = r.get("scores_b", {}).get("overall_quality", 0)
        deltas.append((r, oa - ob))

    sorted_deltas = sorted(deltas, key=lambda x: x[1], reverse=True)
    biggest_a_wins = sorted_deltas[:3]
    biggest_b_wins = sorted_deltas[-3:][::-1]  # reverse so biggest B win is first

    # ── Determine overall winner ──
    if composite_a > composite_b + 0.1:
        winner_text = f"**{prompt_a_name}** wins overall (composite {composite_a:.2f} vs {composite_b:.2f})"
    elif composite_b > composite_a + 0.1:
        winner_text = f"**{prompt_b_name}** wins overall (composite {composite_b:.2f} vs {composite_a:.2f})"
    else:
        winner_text = f"**Tie** — composite scores are nearly equal ({composite_a:.2f} vs {composite_b:.2f})"

    # ── Build markdown report ──
    lines = []
    lines.append("# 3ioNetra — Prompt A/B Test Report")
    lines.append("")

    # Section 1: Configuration
    lines.append("## 1. Test Configuration")
    lines.append("")
    lines.append(f"| Parameter | Value |")
    lines.append(f"|-----------|-------|")
    lines.append(f"| Prompt A | `{prompt_a_name}` |")
    lines.append(f"| Prompt B | `{prompt_b_name}` |")
    lines.append(f"| Generation Model | `{settings.GEMINI_MODEL}` |")
    lines.append(f"| Judge Model | `{JUDGE_MODEL}` |")
    lines.append(f"| Date | {datetime.now().strftime('%Y-%m-%d %H:%M')} |")
    lines.append(f"| Scenarios | {total} |")
    lines.append("")

    # Section 2: Overall Winner
    lines.append("## 2. Overall Winner")
    lines.append("")
    lines.append(winner_text)
    lines.append("")
    lines.append(f"Head-to-head overall: A wins {overall_h2h['A']}, B wins {overall_h2h['B']}, ties {overall_h2h['tie']}")
    lines.append("")

    # Section 3: Score Comparison
    lines.append("## 3. Score Comparison (Independent Judge, Mean 1-5)")
    lines.append("")
    lines.append("| Dimension | A | B | Delta | Better |")
    lines.append("|-----------|---|---|-------|--------|")
    for key in SCORE_KEYS:
        label = key.replace("_", " ").title()
        a_val = means_a[key]
        b_val = means_b[key]
        delta = a_val - b_val
        better = "A" if delta > 0.05 else ("B" if delta < -0.05 else "=")
        lines.append(f"| {label} | {a_val:.2f} | {b_val:.2f} | {delta:+.2f} | {better} |")
    lines.append(f"| **Composite** | **{composite_a:.2f}** | **{composite_b:.2f}** | **{composite_a - composite_b:+.2f}** | {'A' if composite_a > composite_b + 0.05 else ('B' if composite_b > composite_a + 0.05 else '=')} |")
    lines.append("")

    # Section 4: Head-to-Head Win Rates
    lines.append("## 4. Head-to-Head Win Rates")
    lines.append("")
    lines.append("| Dimension | A Wins | B Wins | Ties |")
    lines.append("|-----------|--------|--------|------|")
    for key in H2H_KEYS:
        label = key.replace("_winner", "").replace("_", " ").title()
        c = h2h_counts[key]
        bar_a = "#" * c["A"]
        bar_b = "#" * c["B"]
        lines.append(f"| {label} | {c['A']} ({bar_a}) | {c['B']} ({bar_b}) | {c['tie']} |")
    lines.append("")

    # Section 5: Format Compliance
    lines.append("## 5. Format Compliance")
    lines.append("")
    lines.append("| Check | A Pass% | B Pass% |")
    lines.append("|-------|---------|---------|")
    for check in format_checks_list:
        label = check.replace("_", " ").title()
        lines.append(f"| {label} | {fmt_a[check]:.0f}% | {fmt_b[check]:.0f}% |")
    lines.append("")

    # Section 6: Per-Category Breakdown
    lines.append("## 6. Per-Category Breakdown")
    lines.append("")
    lines.append("| Category | N | A Avg | B Avg | H2H A | H2H B | Winner |")
    lines.append("|----------|---|-------|-------|-------|-------|--------|")
    for cat in sorted(cat_summary.keys()):
        s = cat_summary[cat]
        cat_winner = "A" if s["a_avg"] > s["b_avg"] + 0.1 else ("B" if s["b_avg"] > s["a_avg"] + 0.1 else "=")
        lines.append(
            f"| {cat.title()} | {s['count']} | {s['a_avg']:.2f} | {s['b_avg']:.2f} "
            f"| {s['h2h_a']} | {s['h2h_b']} | {cat_winner} |"
        )
    lines.append("")

    # Section 7: Biggest Wins for A
    lines.append("## 7. Biggest Wins for A")
    lines.append("")
    for r, delta in biggest_a_wins:
        if delta <= 0:
            continue
        lines.append(f"- **Scenario {r.get('id', '?')}** ({r.get('category', '')}) — delta +{delta:.1f}")
        lines.append(f"  - Q: {r.get('question', '')[:80]}")
        lines.append(f"  - A scored {r.get('scores_a', {}).get('overall_quality', 0)}, B scored {r.get('scores_b', {}).get('overall_quality', 0)}")
    lines.append("")

    # Section 8: Biggest Wins for B
    lines.append("## 8. Biggest Wins for B")
    lines.append("")
    for r, delta in biggest_b_wins:
        if delta >= 0:
            continue
        lines.append(f"- **Scenario {r.get('id', '?')}** ({r.get('category', '')}) — delta {delta:.1f}")
        lines.append(f"  - Q: {r.get('question', '')[:80]}")
        lines.append(f"  - A scored {r.get('scores_a', {}).get('overall_quality', 0)}, B scored {r.get('scores_b', {}).get('overall_quality', 0)}")
    lines.append("")

    # Section 9: Detailed Per-Scenario Results
    lines.append("## 9. Detailed Per-Scenario Results")
    lines.append("")
    for r in results:
        sid = r.get("id", "?")
        lines.append(f"### Scenario {sid}: {r.get('category', '').title()}")
        lines.append(f"**Q:** {r.get('question', '')}")
        lines.append(f"**Phase:** {r.get('phase', '')}")
        lines.append("")

        sa = r.get("scores_a", {})
        sb = r.get("scores_b", {})
        lines.append("| Dim | A | B |")
        lines.append("|-----|---|---|")
        for key in SCORE_KEYS:
            lines.append(f"| {key.replace('_', ' ').title()} | {sa.get(key, 0)} | {sb.get(key, 0)} |")

        h2h = r.get("h2h_verdict", {})
        lines.append(f"\n**H2H:** overall={h2h.get('overall_winner', '?')}, tone={h2h.get('tone_winner', '?')}, dharmic={h2h.get('dharmic_winner', '?')}, clarity={h2h.get('clarity_winner', '?')}")
        lines.append(f"**Reasoning:** {h2h.get('reasoning', 'N/A')}")
        lines.append("")

        lines.append(f"<details><summary>Response A ({prompt_a_name})</summary>\n\n{r.get('response_a', '')[:500]}\n</details>")
        lines.append(f"<details><summary>Response B ({prompt_b_name})</summary>\n\n{r.get('response_b', '')[:500]}\n</details>")
        lines.append("")
        lines.append("---")
        lines.append("")

    report_text = "\n".join(lines)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(report_text)
    logger.info(f"Report saved to {REPORT_FILE}")

    return report_text


# ── CLI ─────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="3ioNetra Prompt A/B Tester — compare two prompt YAML versions side-by-side",
    )
    parser.add_argument(
        "--prompt-a", required=True,
        help="Name of first prompt YAML (e.g. spiritual_mitra)",
    )
    parser.add_argument(
        "--prompt-b", required=True,
        help="Name of second prompt YAML (e.g. spiritual_mitra_v5.3)",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Resume a previously interrupted run",
    )
    parser.add_argument(
        "--category",
        help="Run only scenarios in this category (e.g. grief, career, family)",
    )
    args = parser.parse_args()

    run_ab_test(
        prompt_a_name=args.prompt_a,
        prompt_b_name=args.prompt_b,
        resume=args.resume,
        category_filter=args.category,
    )


if __name__ == "__main__":
    main()
