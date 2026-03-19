"""
Quick diya-bias test — sends 5 diverse scenarios through the updated prompt
and checks if responses show practice variety (not always diya/lamp).

Usage: cd backend && venv/bin/python3 tests/test_diya_bias.py
"""

import os
import sys
import re
import time

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from config import settings
from services.prompt_manager import PromptManager

# ── Scenarios covering different life domains ──
SCENARIOS = [
    {
        "id": "career_stress",
        "message": "I've been working 14 hour days and my boss doesn't even notice. I feel so burnt out.",
        "domain": "career",
        "phase": "guidance",
    },
    {
        "id": "grief",
        "message": "It's been six months since my grandmother passed. Some days the sadness just hits me out of nowhere.",
        "domain": "grief",
        "phase": "guidance",
    },
    {
        "id": "anxiety",
        "message": "I can't stop overthinking about everything. My mind just won't shut off at night.",
        "domain": "anxiety",
        "phase": "guidance",
    },
    {
        "id": "hanuman_devotee",
        "message": "I feel like I've lost all my courage. Nothing scares me more than failure right now.",
        "domain": "career",
        "phase": "guidance",
        "preferred_deity": "Hanuman",
    },
    {
        "id": "relationship",
        "message": "My husband and I barely talk anymore. We just exist in the same house like strangers.",
        "domain": "relationships",
        "phase": "guidance",
    },
]


def main():
    from google import genai
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    prompt_dir = os.path.join(BACKEND_DIR, "prompts")
    pm = PromptManager(prompt_dir)
    system_instruction = pm.get_prompt("spiritual_mitra", "system_instruction")
    phase_instructions = pm.get_prompt("spiritual_mitra", "phase_prompts.guidance", default="")

    results = []
    diya_count = 0

    for sc in SCENARIOS:
        profile_text = ""
        if sc.get("preferred_deity"):
            profile_text = f"\n{'='*60}\nWHO YOU ARE SPEAKING TO:\n{'='*60}\n   - Preferred deity: {sc['preferred_deity']}\n   - Life area: {sc['domain']}\n{'='*60}\n"
        else:
            profile_text = f"\n{'='*60}\nWHO YOU ARE SPEAKING TO:\n{'='*60}\n   - Life area: {sc['domain']}\n{'='*60}\n"

        prompt = f"""{profile_text}

User's message:
{sc['message']}

═══════════════════════════════════════════════════════════
YOUR INSTRUCTIONS FOR THIS PHASE (guidance):
═══════════════════════════════════════════════════════════
{phase_instructions}

BEFORE YOU RESPOND — CHECK THESE:
- Don't open with "I hear you", "It sounds like", "I understand" — say something specific.
- No numbered lists or bullet points. Flowing sentences only.
- Don't end with "How does that sound?" or "Would you like to hear more?" — just end.
- One verse maximum per response, only if it truly fits.
- You are a companion having a real conversation — not a therapist running an assessment.

Your response:"""

        try:
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt.strip(),
                config={
                    "system_instruction": system_instruction,
                    "temperature": 0.7,
                },
            )
            text = response.text.strip() if response.text else "[EMPTY]"
        except Exception as e:
            text = f"[ERROR] {e}"

        has_diya = bool(re.search(r'\bdiya\b|\blamp\b|\bflame\b|\bdeepa\b', text, re.IGNORECASE))
        if has_diya:
            diya_count += 1

        # Detect practice types mentioned
        practice_types = []
        patterns = {
            "diya/lamp": r'\bdiya\b|\blamp\b|\bflame\b|\bdeepa\b',
            "mantra": r'\bmantra\b|\bchant\b|\bjapa\b|\bchalisa\b',
            "pranayama/breath": r'\bpranayama\b|\bbreath\b|\bsaans\b|\bnadi shodhana\b|\bsheetali\b',
            "incense/dhoop": r'\bincense\b|\bdhoop\b|\bagarbatti\b',
            "mala": r'\bmala\b',
            "tilak": r'\btilak\b',
            "temple": r'\btemple\b|\bmandir\b',
            "meditation": r'\bmeditat\b|\bdhyan\b',
            "seva": r'\bseva\b|\bservice\b',
            "prayer/puja": r'\bpuja\b|\bprayer\b|\baarti\b',
            "sankalpa": r'\bsankalpa\b|\bintention\b',
        }
        for ptype, pat in patterns.items():
            if re.search(pat, text, re.IGNORECASE):
                practice_types.append(ptype)

        results.append({
            "id": sc["id"],
            "domain": sc["domain"],
            "has_diya": has_diya,
            "practice_types": practice_types,
            "word_count": len(text.split()),
            "response": text,
        })

        print(f"\n{'='*70}")
        print(f"SCENARIO: {sc['id']} (domain: {sc['domain']})")
        if sc.get("preferred_deity"):
            print(f"  Preferred deity: {sc['preferred_deity']}")
        print(f"  Message: {sc['message'][:80]}...")
        print(f"  Diya mentioned: {'YES ⚠️' if has_diya else 'NO ✓'}")
        print(f"  Practice types: {', '.join(practice_types) or 'none detected'}")
        print(f"  Word count: {len(text.split())}")
        print(f"  Response: {text[:200]}...")
        time.sleep(2)

    # Summary
    print(f"\n{'='*70}")
    print("DIYA BIAS TEST SUMMARY")
    print(f"{'='*70}")
    print(f"Scenarios tested: {len(SCENARIOS)}")
    print(f"Responses mentioning diya/lamp/flame: {diya_count}/{len(SCENARIOS)}")

    # Practice diversity
    all_types = set()
    for r in results:
        all_types.update(r["practice_types"])
    print(f"Unique practice types across all responses: {len(all_types)}")
    print(f"Practice types seen: {', '.join(sorted(all_types))}")

    # Check variety
    practice_lists = [tuple(sorted(r["practice_types"])) for r in results]
    unique_combos = len(set(practice_lists))
    print(f"Unique practice combinations: {unique_combos}/{len(SCENARIOS)}")

    if diya_count <= 1:
        print("\n✅ PASS: Diya bias is resolved — diverse practices being recommended")
    elif diya_count <= 2:
        print("\n⚠️  PARTIAL: Some diya mentions remain, but there's decent variety")
    else:
        print("\n❌ FAIL: Diya still appears in {}/5 responses — bias not fully resolved".format(diya_count))


if __name__ == "__main__":
    main()
