"""
Listening Phase Test Suite for 3ioNetra Mitra
==============================================
Validates that the bot stays in listening/clarification phase for the
correct number of turns before transitioning to guidance. Runs 54
multi-turn conversations against the live API and reports premature
transitions, format violations, and content violations.

Transition rules (from companion_engine.py:740-818):
  - High-intensity emotions (sadness, anger, anxiety, hopelessness, grief, despair):
    min 3-4 turns in listening
  - Normal emotions: min 1-2 turns in listening
  - Direct detailed question (>4 words + ? or guidance keyword + NOT high-intensity):
    can bypass turn count
  - Oscillation control: 3 turns spacing between guidance moments
  - Force transition: at turn 6 or readiness >= 0.7
  - Both "listening" and "clarification" count as valid listening-phase indicators

Usage:
    python tests/test_listening_phase.py
    python tests/test_listening_phase.py --case 5
    python tests/test_listening_phase.py --category A
    python tests/test_listening_phase.py --url http://localhost:8080
"""

import asyncio
import httpx
import json
import re
import sys
import time
import argparse
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DEFAULT_BASE_URL = "http://localhost:8080"
TEST_EMAIL = "test_listening_eval@test.com"
TEST_PASSWORD = "TestListening2026!"
TEST_NAME = "Listening Phase Evaluator"
RESULTS_DIR = Path(__file__).parent / "listening_phase_results"
REQUEST_TIMEOUT = 90.0
INTER_TURN_DELAY = 2.0  # seconds between turns

VALID_LISTENING_PHASES = ["listening", "clarification"]

# From backend/constants.py
HOLLOW_PHRASES = (
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
)

FORMULAIC_ENDINGS = (
    "how does that sound?",
    "would you like to hear more?",
    "does this resonate?",
    "does that make sense?",
    "shall i continue?",
    "would you like me to elaborate?",
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class Validation:
    check_type: str
    params: dict = field(default_factory=dict)
    description: str = ""


@dataclass
class ListeningMeta:
    min_listening_turns: int  # turns that MUST be listening
    high_intensity: bool = False


@dataclass
class Turn:
    user_message: str
    validations: list[Validation] = field(default_factory=list)


@dataclass
class TestCase:
    id: int
    category: str
    title: str
    persona: dict
    turns: list[Turn]
    listening_meta: ListeningMeta
    description: str = ""


@dataclass
class TurnResult:
    turn_number: int
    user_message: str
    bot_response: str
    phase: str
    signals: dict
    turn_count: int
    recommended_products: list
    flow_metadata: dict
    validation_results: list[dict]  # [{description, passed, detail}]
    error: str = ""


@dataclass
class CaseResult:
    case_id: int
    category: str
    title: str
    turn_results: list[TurnResult]
    listening_meta: ListeningMeta = field(default_factory=lambda: ListeningMeta(min_listening_turns=2))
    first_guidance_turn: int = 0  # 0 = never transitioned
    min_listening_met: bool = True
    passed: int = 0
    failed: int = 0
    errors: int = 0
    error: str = ""


# ---------------------------------------------------------------------------
# Personas (same as conversational_test_runner.py)
# ---------------------------------------------------------------------------
PERSONAS = {
    "arjun": {
        "name": "Arjun",
        "age_group": "30-40",
        "gender": "male",
        "profession": "Software Engineer",
        "preferred_deity": "Shiva",
        "location": "Bangalore, India",
        "spiritual_interests": ["meditation", "yoga", "vedanta"],
    },
    "meera": {
        "name": "Meera",
        "age_group": "50-60",
        "gender": "female",
        "profession": "Teacher",
        "preferred_deity": "Krishna",
        "location": "Delhi, India",
        "spiritual_interests": ["bhakti", "kirtan", "temples"],
    },
    "rohan": {
        "name": "Rohan",
        "age_group": "18-25",
        "gender": "male",
        "profession": "University Student",
        "preferred_deity": "Hanuman",
        "location": "Mumbai, India",
        "spiritual_interests": ["strength", "discipline", "service"],
    },
    "priya": {
        "name": "Priya",
        "age_group": "25-35",
        "gender": "female",
        "profession": "Marketing Manager",
        "preferred_deity": "Durga",
        "location": "Hyderabad, India",
        "spiritual_interests": ["meditation", "chakras", "temples"],
    },
    "vikram": {
        "name": "Vikram",
        "age_group": "60+",
        "gender": "male",
        "profession": "Retired Banker",
        "preferred_deity": "Ram",
        "location": "Pune, India",
        "spiritual_interests": ["dharma", "philosophy", "charity"],
    },
    "ananya": {
        "name": "Ananya",
        "age_group": "18-25",
        "gender": "female",
        "profession": "College Student",
        "preferred_deity": "Saraswati",
        "location": "Jaipur, India",
        "spiritual_interests": ["knowledge", "arts", "meditation"],
    },
}


# ---------------------------------------------------------------------------
# Validation engine
# ---------------------------------------------------------------------------
def run_validation(v: Validation, response: str, api_data: dict) -> dict:
    """Run a single validation check. Returns {description, passed, detail}."""
    result = {"description": v.description or v.check_type, "passed": False, "detail": ""}

    try:
        if v.check_type == "max_words":
            limit = v.params["n"]
            word_count = len(response.split())
            result["passed"] = word_count <= limit
            result["detail"] = f"{word_count} words (limit {limit})"

        elif v.check_type == "min_words":
            minimum = v.params["n"]
            word_count = len(response.split())
            result["passed"] = word_count >= minimum
            result["detail"] = f"{word_count} words (min {minimum})"

        elif v.check_type == "must_contain":
            text = v.params["text"].lower()
            result["passed"] = text in response.lower()
            result["detail"] = f"looking for '{text}'"

        elif v.check_type == "must_contain_any":
            texts = [t.lower() for t in v.params["texts"]]
            found = [t for t in texts if t in response.lower()]
            result["passed"] = len(found) > 0
            result["detail"] = f"found: {found}" if found else f"none of {texts}"

        elif v.check_type == "must_not_contain":
            text = v.params["text"].lower()
            result["passed"] = text not in response.lower()
            result["detail"] = f"checking absence of '{text}'"

        elif v.check_type == "must_not_contain_any":
            texts = [t.lower() for t in v.params["texts"]]
            found = [t for t in texts if t in response.lower()]
            result["passed"] = len(found) == 0
            result["detail"] = f"unwanted found: {found}" if found else "clean"

        elif v.check_type == "phase_equals":
            expected = v.params["phase"]
            actual = api_data.get("phase", "")
            result["passed"] = actual == expected
            result["detail"] = f"expected '{expected}', got '{actual}'"

        elif v.check_type == "phase_in":
            allowed = v.params["phases"]
            actual = api_data.get("phase", "")
            result["passed"] = actual in allowed
            result["detail"] = f"expected one of {allowed}, got '{actual}'"

        elif v.check_type == "no_markdown":
            md_patterns = [
                r"^#{1,6}\s",      # headers
                r"^\s*[-*]\s",     # bullet points
                r"^\d+\.\s",      # numbered lists
                r"\*\*[^*]+\*\*", # bold
            ]
            violations = []
            for line in response.split("\n"):
                for pat in md_patterns:
                    if re.search(pat, line):
                        violations.append(line.strip()[:60])
                        break
            result["passed"] = len(violations) == 0
            result["detail"] = f"violations: {violations[:3]}" if violations else "clean"

        elif v.check_type == "no_hollow_phrases":
            found = [h for h in HOLLOW_PHRASES if h in response.lower()]
            result["passed"] = len(found) == 0
            result["detail"] = f"found: {found}" if found else "clean"

        elif v.check_type == "response_not_empty":
            result["passed"] = len(response.strip()) > 0
            result["detail"] = f"{len(response)} chars"

        elif v.check_type == "no_product_urls":
            url_patterns = ["my3ionetra.com", "3ionetra.com/product", "http", "www."]
            found = [p for p in url_patterns if p in response.lower()]
            result["passed"] = len(found) == 0
            result["detail"] = f"found URLs: {found}" if found else "clean"

        elif v.check_type == "signal_contains":
            key = v.params["key"]
            value = v.params.get("value", "").lower()
            signals = api_data.get("signals_collected", {})
            actual = str(signals.get(key, "")).lower()
            if value:
                result["passed"] = value in actual
                result["detail"] = f"signal '{key}'='{actual}', expected '{value}'"
            else:
                result["passed"] = key in signals and signals[key]
                result["detail"] = f"signal '{key}'='{actual}'" if key in signals else f"signal '{key}' missing"

        else:
            result["detail"] = f"unknown check type: {v.check_type}"

    except Exception as e:
        result["detail"] = f"validation error: {e}"

    return result


# ---------------------------------------------------------------------------
# Standard validations for every listening-phase turn
# ---------------------------------------------------------------------------
def get_listening_turn_validations() -> list[Validation]:
    """Validations applied to every turn expected to be in listening phase."""
    return [
        Validation("response_not_empty", description="Response is non-empty"),
        Validation("phase_in", {"phases": VALID_LISTENING_PHASES}, "Phase is listening/clarification"),
        Validation("no_markdown", description="No markdown formatting"),
        Validation("no_hollow_phrases", description="No hollow/banned phrases"),
        Validation("no_product_urls", description="No product URLs in text"),
        Validation("must_not_contain", {"text": "[VERSE]"}, "No premature scripture [VERSE] tag"),
        Validation("must_not_contain", {"text": "[MANTRA]"}, "No premature [MANTRA] tag"),
        Validation("max_words", {"n": 120}, "Response under 120 words"),
    ]


# ---------------------------------------------------------------------------
# 54 Test Cases (7 categories: A–G)
# ---------------------------------------------------------------------------
ALL_TEST_CASES: list[TestCase] = [

    # ===================================================================
    # CATEGORY A: Pure Emotional Venting (10 cases, 4-5 turns each)
    # Messages are pure emotional sharing, no questions.
    # ===================================================================

    # A1: Workplace frustration (arjun, 4 turns, normal)
    TestCase(
        id=1, category="A", title="Workplace Frustration",
        persona=PERSONAS["arjun"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="Pure venting about work stress, no questions asked.",
        turns=[
            Turn("hey"),
            Turn("office mein aaj phir se bahut frustrating day tha"),
            Turn("boss ne meri presentation reject kar di bina reason bataye"),
            Turn("feel like nothing I do is ever enough for these people"),
        ],
    ),

    # A2: Loneliness after moving (rohan, 4 turns, normal)
    TestCase(
        id=2, category="A", title="Loneliness After Moving",
        persona=PERSONAS["rohan"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="Venting about loneliness in a new city.",
        turns=[
            Turn("hi"),
            Turn("shifted to pune last month for internship. dont know anyone here"),
            Turn("roommates are ok but not friends. i eat alone everyday"),
            Turn("missing home a lot. maa ki yaad aati hai"),
        ],
    ),

    # A3: Aging parents (meera, 5 turns, HIGH - sadness)
    TestCase(
        id=3, category="A", title="Aging Parents — Deep Sadness",
        persona=PERSONAS["meera"],
        listening_meta=ListeningMeta(min_listening_turns=4, high_intensity=True),
        description="Watching parents age and decline, deep sadness.",
        turns=[
            Turn("namaste"),
            Turn("pitaji ki tabiyat bahut kharab hoti ja rahi hai"),
            Turn("pehle itne strong the. ab bistar se uthna mushkil hai"),
            Turn("unhe takleef mein dekh kar rona aata hai"),
            Turn("maa bhi thak gayi hai unki seva karte karte"),
        ],
    ),

    # A4: Frustration with spouse (priya, 5 turns, HIGH - anger)
    TestCase(
        id=4, category="A", title="Frustration with Spouse — Anger",
        persona=PERSONAS["priya"],
        listening_meta=ListeningMeta(min_listening_turns=4, high_intensity=True),
        description="Intense anger about spouse not contributing at home.",
        turns=[
            Turn("hello"),
            Turn("i am SO done with my husband. he does NOTHING at home"),
            Turn("i work full time, cook, clean, manage the kids. he just watches tv"),
            Turn("when i ask for help he says im nagging. NAGGING? really?"),
            Turn("i feel like a servant in my own house"),
        ],
    ),

    # A5: Financial stress (arjun, 5 turns, HIGH - anxiety)
    TestCase(
        id=5, category="A", title="Financial Stress — Anxiety",
        persona=PERSONAS["arjun"],
        listening_meta=ListeningMeta(min_listening_turns=4, high_intensity=True),
        description="Severe financial anxiety with EMIs and debt.",
        turns=[
            Turn("hi"),
            Turn("financial situation bahut kharab hai. EMIs manage nahi ho rahi"),
            Turn("credit card debt badh raha hai. wife ko bata nahi sakta"),
            Turn("raat ko neend nahi aati sochte sochte"),
            Turn("lagta hai main kabhi iss debt se bahar nahi aa paunga"),
        ],
    ),

    # A6: Pet loss (rohan, 5 turns, HIGH - grief)
    TestCase(
        id=6, category="A", title="Pet Loss — Grief",
        persona=PERSONAS["rohan"],
        listening_meta=ListeningMeta(min_listening_turns=4, high_intensity=True),
        description="Grieving the loss of a pet dog.",
        turns=[
            Turn("hey"),
            Turn("my dog bruno died yesterday. he was with me since i was 10"),
            Turn("everyone says its just a dog. but he was my best friend"),
            Turn("his bed is still in my room. i keep looking at it"),
            Turn("12 years of unconditional love just gone"),
        ],
    ),

    # A7: Self-disappointment (priya, 4 turns, normal)
    TestCase(
        id=7, category="A", title="Self-Disappointment",
        persona=PERSONAS["priya"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="Feeling disappointed with self, not meeting own expectations.",
        turns=[
            Turn("hi"),
            Turn("i keep setting goals and never meeting them"),
            Turn("started gym, quit. started reading, quit. started cooking, quit"),
            Turn("i just cant stick with anything. maybe im just lazy"),
        ],
    ),

    # A8: Overwhelm multiple issues (vikram, 4 turns, normal)
    TestCase(
        id=8, category="A", title="Overwhelm — Multiple Issues",
        persona=PERSONAS["vikram"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="Feeling overwhelmed by multiple problems at once.",
        turns=[
            Turn("pranam"),
            Turn("sab kuch ek saath ho raha hai. health, family, paisa sab"),
            Turn("bete ka career tension, biwi ki tabiyat, aur mera BP"),
            Turn("samajh nahi aata pehle kya sambhalu"),
        ],
    ),

    # A9: Jealousy and comparison (rohan, 4 turns, normal)
    TestCase(
        id=9, category="A", title="Jealousy and Comparison",
        persona=PERSONAS["rohan"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="Feeling jealous of peers doing better.",
        turns=[
            Turn("yo"),
            Turn("all my friends from school are doing so well. one got into iim one is in google"),
            Turn("and here i am struggling with basic placements"),
            Turn("its hard not to compare. feels like im falling behind in life"),
        ],
    ),

    # A10: Restlessness (meera, 4 turns, normal)
    TestCase(
        id=10, category="A", title="Restlessness — Can't Sit Still",
        persona=PERSONAS["meera"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="Feeling restless and unsettled without clear reason.",
        turns=[
            Turn("namaste"),
            Turn("mann bahut bechain hai aajkal. koi khas reason bhi nahi hai"),
            Turn("raat ko neend nahi aati. din mein concentrate nahi hota"),
            Turn("pooja mein bhi mann nahi lagta. bahut ajeeb feeling hai"),
        ],
    ),

    # ===================================================================
    # CATEGORY B: High-Intensity Emotions (10 cases, 5 turns each)
    # Grief, anger, anxiety, hopelessness, despair. Min listening: 4-5 turns.
    # ===================================================================

    # B1: Death of mother (meera, 5 turns, HIGH - grief)
    TestCase(
        id=11, category="B", title="Death of Mother — Grief",
        persona=PERSONAS["meera"],
        listening_meta=ListeningMeta(min_listening_turns=4, high_intensity=True),
        description="Raw grief over loss of mother.",
        turns=[
            Turn("namaste"),
            Turn("meri maa ka kal dehant ho gaya"),
            Turn("unke bina ghar kitna soona lag raha hai"),
            Turn("subah uthke chai banane gayi toh yaad aaya ki woh nahi hain"),
            Turn("dil bahut bhari hai. kisi se baat karne ka mann nahi"),
        ],
    ),

    # B2: Betrayal by best friend (arjun, 5 turns, HIGH - anger)
    TestCase(
        id=12, category="B", title="Betrayal by Best Friend — Anger",
        persona=PERSONAS["arjun"],
        listening_meta=ListeningMeta(min_listening_turns=4, high_intensity=True),
        description="Intense anger after best friend's betrayal.",
        turns=[
            Turn("hey"),
            Turn("my best friend of 15 years stabbed me in the back"),
            Turn("he went behind my back and told my boss about my side project"),
            Turn("i trusted him with everything. he knew this could get me fired"),
            Turn("i dont think i can ever trust anyone again"),
        ],
    ),

    # B3: Health scare (vikram, 5 turns, HIGH - anxiety)
    TestCase(
        id=13, category="B", title="Health Scare — Anxiety",
        persona=PERSONAS["vikram"],
        listening_meta=ListeningMeta(min_listening_turns=4, high_intensity=True),
        description="Severe anxiety after concerning medical results.",
        turns=[
            Turn("pranam"),
            Turn("doctor ne bola reports mein kuch gadbad hai. aur tests chahiye"),
            Turn("cancer ka dar lag raha hai. mere bade bhai ko tha"),
            Turn("raat ko sochte sochte haath kaapne lagte hain"),
            Turn("bachche abhi chhote hain. agar mujhe kuch ho gaya toh"),
        ],
    ),

    # B4: Career hopelessness (rohan, 5 turns, HIGH - hopelessness)
    TestCase(
        id=14, category="B", title="Career Hopelessness",
        persona=PERSONAS["rohan"],
        listening_meta=ListeningMeta(min_listening_turns=4, high_intensity=True),
        description="Complete hopelessness about career prospects.",
        turns=[
            Turn("hey"),
            Turn("50 applications. zero calls. not even a rejection email"),
            Turn("my batch mates all have jobs. im sitting at home"),
            Turn("papa ka expression dekh kar guilt hota hai. unka paisa waste kiya"),
            Turn("sometimes i think im just not meant for success"),
        ],
    ),

    # B5: Breakup despair (priya, 5 turns, HIGH - despair)
    TestCase(
        id=15, category="B", title="Breakup Despair",
        persona=PERSONAS["priya"],
        listening_meta=ListeningMeta(min_listening_turns=4, high_intensity=True),
        description="Despair after a devastating breakup.",
        turns=[
            Turn("hi"),
            Turn("he left me for someone else. after 5 years together"),
            Turn("i gave up so much for this relationship. my friends my hobbies my career growth"),
            Turn("now i have nothing. no one. just an empty apartment"),
            Turn("i dont even know who i am without him anymore"),
        ],
    ),

    # B6: Miscarriage grief (priya, 5 turns, HIGH - grief)
    TestCase(
        id=16, category="B", title="Miscarriage Grief",
        persona=PERSONAS["priya"],
        listening_meta=ListeningMeta(min_listening_turns=4, high_intensity=True),
        description="Grief after a miscarriage, compounded by others minimizing it.",
        turns=[
            Turn("hello"),
            Turn("i had a miscarriage last week. 4 months along"),
            Turn("everyone says at least it was early. but i already loved that baby"),
            Turn("i had names picked out. the nursery was half done"),
            Turn("my body feels broken. my heart feels broken"),
        ],
    ),

    # B7: Workplace injustice (arjun, 5 turns, HIGH - anger)
    TestCase(
        id=17, category="B", title="Workplace Injustice — Rage",
        persona=PERSONAS["arjun"],
        listening_meta=ListeningMeta(min_listening_turns=4, high_intensity=True),
        description="Seething anger about workplace discrimination.",
        turns=[
            Turn("namaste"),
            Turn("they promoted a guy who joined 6 months ago over me. 3 years I've been here"),
            Turn("he's the VP's nephew. everyone knows it. nobody says anything"),
            Turn("HR told me to 'be patient'. BE PATIENT? i've been patient for 3 years"),
            Turn("i want to smash my laptop and walk out. this is SO unfair"),
        ],
    ),

    # B8: Child safety anxiety (meera, 5 turns, HIGH - anxiety)
    TestCase(
        id=18, category="B", title="Child Safety Anxiety",
        persona=PERSONAS["meera"],
        listening_meta=ListeningMeta(min_listening_turns=4, high_intensity=True),
        description="Mother's overwhelming anxiety about child's safety.",
        turns=[
            Turn("namaste"),
            Turn("beti akeli abroad gayi hai. bahut tension ho rahi hai"),
            Turn("news mein itni buri cheezein dikhate hain. dar lagta hai"),
            Turn("woh phone nahi uthati toh dil doobne lagta hai"),
            Turn("raat ko baar baar uthti hoon check karne ki koi message aaya ki nahi"),
        ],
    ),

    # B9: Spousal death + guilt (vikram, 5 turns, HIGH - grief)
    TestCase(
        id=19, category="B", title="Spousal Death with Guilt",
        persona=PERSONAS["vikram"],
        listening_meta=ListeningMeta(min_listening_turns=4, high_intensity=True),
        description="Grief after wife's death compounded by guilt.",
        turns=[
            Turn("pranam"),
            Turn("patni ka dehant ho gaya. 40 saal ka saath tha"),
            Turn("unke last din mein hospital nahi tha. office mein tha"),
            Turn("yeh guilt kabhi nahi jayega. jab zaroorat thi tab nahi tha"),
            Turn("ab ghar mein akela baithta hoon aur unse maafi maangta hoon"),
        ],
    ),

    # B10: Life direction despair (rohan, 5 turns, HIGH - despair)
    TestCase(
        id=20, category="B", title="Life Direction Despair",
        persona=PERSONAS["rohan"],
        listening_meta=ListeningMeta(min_listening_turns=4, high_intensity=True),
        description="Complete despair about direction in life.",
        turns=[
            Turn("hey"),
            Turn("i genuinely dont know what the point of anything is"),
            Turn("22 years old and i have no passion no skills no direction"),
            Turn("everyone around me seems to know what they want. i just exist"),
            Turn("waking up every day feels pointless"),
        ],
    ),

    # ===================================================================
    # CATEGORY C: Gradual Opening Up (8 cases, 4 turns each)
    # Start vague, get specific. Min listening: 3 turns.
    # ===================================================================

    # C1: Career concern — vague to specific
    TestCase(
        id=21, category="C", title="Vague to Specific — Career",
        persona=PERSONAS["arjun"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="Starts vague, gradually reveals career concern.",
        turns=[
            Turn("hi"),
            Turn("kuch theek nahi chal raha"),
            Turn("work pe bahut pressure hai actually"),
            Turn("deadline pe deadline. sleep nahi ho rahi. body toot rahi hai"),
        ],
    ),

    # C2: Relationship — vague to specific
    TestCase(
        id=22, category="C", title="Vague to Specific — Relationship",
        persona=PERSONAS["priya"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="Starts vague, gradually reveals relationship issue.",
        turns=[
            Turn("hello"),
            Turn("life mein bahut confused hoon"),
            Turn("actually its about my relationship"),
            Turn("we've been fighting everyday and im not sure we should stay together"),
        ],
    ),

    # C3: Family conflict — vague to specific
    TestCase(
        id=23, category="C", title="Vague to Specific — Family",
        persona=PERSONAS["meera"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="Starts vague, gradually reveals family conflict.",
        turns=[
            Turn("namaste"),
            Turn("mann udas hai aaj"),
            Turn("ghar mein ek situation hai jo bahut tense hai"),
            Turn("bete ne shaadi kar li bina bataye. ab ghar mein koi baat nahi karta"),
        ],
    ),

    # C4: Health worry — vague to specific
    TestCase(
        id=24, category="C", title="Vague to Specific — Health",
        persona=PERSONAS["vikram"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="Starts vague, gradually reveals health worry.",
        turns=[
            Turn("pranam"),
            Turn("aaj tabiyat theek nahi lag rahi"),
            Turn("actually bahut dino se ek problem hai"),
            Turn("chest mein dard hota hai kabhi kabhi. doctor ko nahi dikhaya"),
        ],
    ),

    # C5: Spiritual doubt — vague to specific
    TestCase(
        id=25, category="C", title="Vague to Specific — Spiritual",
        persona=PERSONAS["ananya"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="Starts vague, gradually reveals spiritual doubt.",
        turns=[
            Turn("hii"),
            Turn("kuch aise thoughts aa rahe hain jo share karne mein darr lagta hai"),
            Turn("its about god and faith actually"),
            Turn("i used to believe in everything but now i feel like prayers dont work"),
        ],
    ),

    # C6: Academic pressure — vague to specific
    TestCase(
        id=26, category="C", title="Vague to Specific — Academic",
        persona=PERSONAS["rohan"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="Starts vague, gradually reveals exam failure.",
        turns=[
            Turn("yo"),
            Turn("just having a really bad time"),
            Turn("its about college"),
            Turn("failed my semester exams. 3 backlogs. papa ko bataya nahi abhi tak"),
        ],
    ),

    # C7: Existential concern — vague to specific
    TestCase(
        id=27, category="C", title="Vague to Specific — Existential",
        persona=PERSONAS["arjun"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="Starts vague, gradually reveals existential emptiness.",
        turns=[
            Turn("namaste"),
            Turn("bas aise hi aaya. koi khas reason nahi"),
            Turn("actually ek baat hai... lagta hai life mein kuch missing hai"),
            Turn("good job hai money hai but andar se empty feel karta hoon"),
        ],
    ),

    # C8: Friendship betrayal — vague to specific
    TestCase(
        id=28, category="C", title="Vague to Specific — Friendship",
        persona=PERSONAS["ananya"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="Starts vague, gradually reveals being backstabbed by friend.",
        turns=[
            Turn("hey"),
            Turn("people suck"),
            Turn("my best friend shared my secrets with everyone"),
            Turn("i told her about my family problems in confidence and now everyone knows"),
        ],
    ),

    # ===================================================================
    # CATEGORY D: Rhetorical Questions (8 cases, 4 turns each)
    # Emotional questions that are NOT guidance requests. Min listening: 3.
    # ===================================================================

    # D1: "Why does this happen to me"
    TestCase(
        id=29, category="D", title="Why Me — Rhetorical",
        persona=PERSONAS["priya"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="Rhetorical 'why me' questions — not seeking guidance.",
        turns=[
            Turn("hi"),
            Turn("why does everything bad happen to me"),
            Turn("first the job then the relationship now my health"),
            Turn("god really has it out for me or something"),
        ],
    ),

    # D2: "How is this fair"
    TestCase(
        id=30, category="D", title="How Is This Fair — Rhetorical",
        persona=PERSONAS["rohan"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="Rhetorical 'how is this fair' — emotional not informational.",
        turns=[
            Turn("hey"),
            Turn("how is it fair that bad people get everything and good people suffer"),
            Turn("i see corrupt people thriving while honest ones struggle"),
            Turn("it makes me question everything i was taught about dharma"),
        ],
    ),

    # D3: "What did I do wrong"
    TestCase(
        id=31, category="D", title="What Did I Do Wrong — Rhetorical",
        persona=PERSONAS["meera"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="Self-blaming rhetorical question — not seeking advice.",
        turns=[
            Turn("namaste"),
            Turn("maine kya galat kiya jo yeh sab ho raha hai"),
            Turn("poori zindagi dharam se jeeli. phir bhi yeh dukh"),
            Turn("shayad meri kismat hi kharab hai"),
        ],
    ),

    # D4: "Will this pain ever end"
    TestCase(
        id=32, category="D", title="Will This Pain Ever End — Rhetorical",
        persona=PERSONAS["arjun"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="Desperate rhetorical — expressing pain not seeking timeline.",
        turns=[
            Turn("namaste"),
            Turn("will this feeling ever go away"),
            Turn("every day is the same heaviness. same emptiness"),
            Turn("i used to be happy. i dont even remember what that feels like"),
        ],
    ),

    # D5: "Why did god do this"
    TestCase(
        id=33, category="D", title="Why Did God Do This — Rhetorical",
        persona=PERSONAS["vikram"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="Questioning god rhetorically — not seeking theological answer.",
        turns=[
            Turn("pranam"),
            Turn("bhagwan ne yeh kyu kiya mere saath"),
            Turn("poori zindagi pooja ki. vrat rakhe. daan diya"),
            Turn("phir bhi itna dukh diya. kya galti thi meri"),
        ],
    ),

    # D6: "Am I not good enough"
    TestCase(
        id=34, category="D", title="Am I Not Good Enough — Rhetorical",
        persona=PERSONAS["ananya"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="Self-doubt question — emotional not seeking reassurance.",
        turns=[
            Turn("hii"),
            Turn("am i just not good enough for anyone"),
            Turn("every relationship every friendship i mess it up somehow"),
            Turn("maybe theres something fundamentally wrong with me"),
        ],
    ),

    # D7: "When will things get better"
    TestCase(
        id=35, category="D", title="When Will Things Get Better — Rhetorical",
        persona=PERSONAS["priya"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="Rhetorical — expressing frustration not seeking prediction.",
        turns=[
            Turn("hello"),
            Turn("when does life start getting better because im waiting"),
            Turn("every month something new goes wrong"),
            Turn("im tired of being strong. im tired of waiting"),
        ],
    ),

    # D8: "Is this all there is"
    TestCase(
        id=36, category="D", title="Is This All There Is — Rhetorical",
        persona=PERSONAS["arjun"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="Existential rhetorical — not seeking philosophical answer.",
        turns=[
            Turn("hi"),
            Turn("is this really all there is to life"),
            Turn("wake up work eat sleep repeat. for what"),
            Turn("even weekends feel empty now"),
        ],
    ),

    # ===================================================================
    # CATEGORY E: Short/Vague Messages (6 cases, 4 turns each)
    # Monosyllabic or minimal responses. Min listening: 3 turns.
    # ===================================================================

    # E1: "bad day"
    TestCase(
        id=37, category="E", title="Short — Bad Day",
        persona=PERSONAS["rohan"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="Minimal messages — 'bad day' type responses.",
        turns=[
            Turn("hey"),
            Turn("bad day"),
            Turn("yeah"),
            Turn("just everything"),
        ],
    ),

    # E2: "idk"
    TestCase(
        id=38, category="E", title="Short — IDK",
        persona=PERSONAS["ananya"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="User giving minimal 'idk' style responses.",
        turns=[
            Turn("hii"),
            Turn("idk whats wrong"),
            Turn("just not feeling it"),
            Turn("hmm"),
        ],
    ),

    # E3: "just sad"
    TestCase(
        id=39, category="E", title="Short — Just Sad",
        persona=PERSONAS["priya"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="Single-phrase emotional statements.",
        turns=[
            Turn("hi"),
            Turn("just sad"),
            Turn("yeah"),
            Turn("dunno why"),
        ],
    ),

    # E4: "complicated"
    TestCase(
        id=40, category="E", title="Short — Complicated",
        persona=PERSONAS["arjun"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="User says 'complicated' and resists elaborating.",
        turns=[
            Turn("hey"),
            Turn("its complicated"),
            Turn("family stuff"),
            Turn("dont wanna get into it"),
        ],
    ),

    # E5: "tired of everything"
    TestCase(
        id=41, category="E", title="Short — Tired",
        persona=PERSONAS["vikram"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="Minimal expressions of exhaustion.",
        turns=[
            Turn("pranam"),
            Turn("thak gaya hoon"),
            Turn("haan"),
            Turn("sab se"),
        ],
    ),

    # E6: "whatever"
    TestCase(
        id=42, category="E", title="Short — Whatever",
        persona=PERSONAS["rohan"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="Dismissive short responses.",
        turns=[
            Turn("yo"),
            Turn("whatever"),
            Turn("doesnt matter"),
            Turn("nothing changes anyway"),
        ],
    ),

    # ===================================================================
    # CATEGORY F: Multi-Domain (8 cases, 4 turns each)
    # Different life areas without guidance-seeking. Min listening: 3.
    # ===================================================================

    # F1: Career burnout
    TestCase(
        id=43, category="F", title="Career Burnout",
        persona=PERSONAS["arjun"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="Career burnout venting, no guidance sought.",
        turns=[
            Turn("hey"),
            Turn("i think im burning out. 12 hour days for 6 months straight"),
            Turn("used to love coding. now i dread opening my laptop"),
            Turn("but there are EMIs and responsibilities so cant just stop"),
        ],
    ),

    # F2: Family conflict
    TestCase(
        id=44, category="F", title="Family Conflict",
        persona=PERSONAS["meera"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="Joint family conflict, emotional venting.",
        turns=[
            Turn("namaste"),
            Turn("ghar mein daily ladai hoti hai. joint family hai"),
            Turn("devar aur pati mein property ka jhagda hai"),
            Turn("main dono ke beech mein phasi hoon"),
        ],
    ),

    # F3: Health concerns
    TestCase(
        id=45, category="F", title="Health Concerns",
        persona=PERSONAS["vikram"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="Multiple health issues causing worry.",
        turns=[
            Turn("pranam"),
            Turn("diabetes hai. BP hai. ab knee ka bhi problem shuru ho gaya"),
            Turn("dawai pe dawai. injection pe injection"),
            Turn("kabhi kabhi lagta hai body hi nahi sath de rahi"),
        ],
    ),

    # F4: Spiritual dryness
    TestCase(
        id=46, category="F", title="Spiritual Dryness",
        persona=PERSONAS["meera"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="Feeling spiritually dry, no interest in practice.",
        turns=[
            Turn("namaste"),
            Turn("pehle pooja mein bahut shanti milti thi. ab nahi milti"),
            Turn("bhajan gaati hoon par mann kahin aur hota hai"),
            Turn("lagta hai bhagwan door ho gaye hain mujhse"),
        ],
    ),

    # F5: Relationship strain
    TestCase(
        id=47, category="F", title="Relationship Strain",
        persona=PERSONAS["priya"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="Relationship slowly falling apart.",
        turns=[
            Turn("hello"),
            Turn("me and my partner barely talk anymore"),
            Turn("we sit in the same room but its like two strangers"),
            Turn("i miss how we used to be but i dont know where it went wrong"),
        ],
    ),

    # F6: Financial pressure
    TestCase(
        id=48, category="F", title="Financial Pressure",
        persona=PERSONAS["rohan"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="Student financial pressure from family.",
        turns=[
            Turn("hey"),
            Turn("education loan ka burden bahut hai. papa ne ghar girvi rakh diya"),
            Turn("agar placement nahi hua toh sab doob jayega"),
            Turn("this pressure is crushing me from inside"),
        ],
    ),

    # F7: Parenting struggle
    TestCase(
        id=49, category="F", title="Parenting Struggle",
        persona=PERSONAS["priya"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="Working mother struggling with parenting guilt.",
        turns=[
            Turn("hi"),
            Turn("my 5 year old said mamma you never have time for me. it broke me"),
            Turn("i work so hard FOR him but he thinks i dont care"),
            Turn("mom guilt is real and its eating me alive"),
        ],
    ),

    # F8: Academic failure
    TestCase(
        id=50, category="F", title="Academic Failure",
        persona=PERSONAS["ananya"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="Failing multiple exams, self-worth affected.",
        turns=[
            Turn("hii"),
            Turn("failed again. third attempt at this entrance exam"),
            Turn("everyone in my batch moved on. im still stuck"),
            Turn("papa ka face dekh kar bahut bura lagta hai"),
        ],
    ),

    # ===================================================================
    # CATEGORY G: Edge Cases (4 cases, 2-4 turns each)
    # ===================================================================

    # G1: Greeting only (2 turns)
    TestCase(
        id=51, category="G", title="Greeting Only — Minimal Interaction",
        persona=PERSONAS["rohan"],
        listening_meta=ListeningMeta(min_listening_turns=2),
        description="User just greets, no emotional content.",
        turns=[
            Turn("hey"),
            Turn("just checking this app out"),
        ],
    ),

    # G2: Long emotional monologue (3 turns)
    TestCase(
        id=52, category="G", title="Long Emotional Monologue",
        persona=PERSONAS["priya"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="User shares a long emotional monologue in one go.",
        turns=[
            Turn("hi"),
            Turn(
                "ok so basically my life is falling apart. my husband wants a divorce, "
                "my mom is sick, i got passed over for promotion, my best friend moved "
                "away, and i havent slept properly in weeks. i dont even know where to "
                "start. everything is happening at once and i feel like im drowning."
            ),
            Turn("sorry for the rant. just needed to let it out"),
        ],
    ),

    # G3: Multiple topics at once (4 turns)
    TestCase(
        id=53, category="G", title="Multiple Topics at Once",
        persona=PERSONAS["vikram"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="User jumps between topics rapidly.",
        turns=[
            Turn("pranam"),
            Turn("aaj subah se bahut kuch ho gaya. bete ne phone nahi uthaya. phir BP badh gaya"),
            Turn("doctor appointment miss ho gayi. aur upar se padosi se bhi jhagda ho gaya"),
            Turn("retirement mein shanti milni chahiye thi par yeh sab kya hai"),
        ],
    ),

    # G4: Crisis-adjacent content (4 turns)
    TestCase(
        id=54, category="G", title="Crisis-Adjacent — Dark Mood",
        persona=PERSONAS["ananya"],
        listening_meta=ListeningMeta(min_listening_turns=3),
        description="Dark mood without explicit crisis language.",
        turns=[
            Turn("hey"),
            Turn("everything feels so dark right now"),
            Turn("like theres no light anywhere. just heaviness"),
            Turn("some days i wonder whats even the point of getting up"),
        ],
    ),
]


# ---------------------------------------------------------------------------
# Runner class
# ---------------------------------------------------------------------------
class ListeningPhaseRunner:
    def __init__(self, base_url: str = DEFAULT_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.token: str | None = None
        self.results: list[CaseResult] = []

    async def authenticate(self, client: httpx.AsyncClient) -> bool:
        """Register or login to get a Bearer token."""
        print(f"\n{'='*70}")
        print(f"  Authenticating with {self.base_url}")
        print(f"{'='*70}")

        # Try login first
        try:
            resp = await client.post(
                f"{self.base_url}/api/auth/login",
                json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
                timeout=30.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                self.token = data.get("token")
                print(f"  Logged in as {TEST_EMAIL}")
                return True
        except Exception:
            pass

        # Try register
        try:
            resp = await client.post(
                f"{self.base_url}/api/auth/register",
                json={
                    "name": TEST_NAME,
                    "email": TEST_EMAIL,
                    "password": TEST_PASSWORD,
                    "gender": "other",
                    "profession": "QA Evaluator",
                    "spiritual_interests": ["testing"],
                },
                timeout=30.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                self.token = data.get("token")
                print(f"  Registered and logged in as {TEST_EMAIL}")
                return True
            else:
                print(f"  Register failed: {resp.status_code} — {resp.text[:200]}")
        except Exception as e:
            print(f"  Register error: {e}")

        # Try login again (in case register failed because user already exists)
        try:
            resp = await client.post(
                f"{self.base_url}/api/auth/login",
                json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
                timeout=30.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                self.token = data.get("token")
                print(f"  Logged in as {TEST_EMAIL}")
                return True
            else:
                print(f"  Login failed: {resp.status_code} — {resp.text[:200]}")
        except Exception as e:
            print(f"  Login error: {e}")

        print("  WARNING: Running without authentication (token=None)")
        return False

    async def run_case(self, client: httpx.AsyncClient, tc: TestCase) -> CaseResult:
        """Run a single test case (multi-turn conversation)."""
        print(f"\n{'─'*70}")
        print(f"  Case #{tc.id}: {tc.title}")
        intensity = "HIGH" if tc.listening_meta.high_intensity else "normal"
        print(f"  Category: {tc.category} | Persona: {tc.persona['name']} | "
              f"Min listen: {tc.listening_meta.min_listening_turns} | Intensity: {intensity}")
        print(f"{'─'*70}")

        case_result = CaseResult(
            case_id=tc.id,
            category=tc.category,
            title=tc.title,
            turn_results=[],
            listening_meta=tc.listening_meta,
        )

        session_id: str | None = None
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        for i, turn in enumerate(tc.turns):
            turn_num = i + 1
            print(f"\n  [{turn_num}] User: {turn.user_message[:80]}")

            payload = {
                "message": turn.user_message,
                "language": "en",
                "user_profile": tc.persona,
            }
            if session_id:
                payload["session_id"] = session_id

            tr = TurnResult(
                turn_number=turn_num,
                user_message=turn.user_message,
                bot_response="",
                phase="",
                signals={},
                turn_count=0,
                recommended_products=[],
                flow_metadata={},
                validation_results=[],
            )

            try:
                resp = await client.post(
                    f"{self.base_url}/api/conversation",
                    json=payload,
                    headers=headers,
                    timeout=REQUEST_TIMEOUT,
                )
                if resp.status_code != 200:
                    tr.error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                    print(f"      ERROR: {tr.error}")
                    case_result.errors += 1
                    case_result.turn_results.append(tr)
                    continue

                data = resp.json()
                session_id = data.get("session_id")
                tr.bot_response = data.get("response", "")
                tr.phase = data.get("phase", "")
                tr.signals = data.get("signals_collected", {})
                tr.turn_count = data.get("turn_count", 0)
                tr.recommended_products = data.get("recommended_products") or []
                tr.flow_metadata = data.get("flow_metadata") or {}

                # Truncate for console
                preview = tr.bot_response[:120].replace("\n", " ")
                print(f"      Bot ({tr.phase}): {preview}...")

                # Track first guidance turn
                if tr.phase == "guidance" and case_result.first_guidance_turn == 0:
                    case_result.first_guidance_turn = turn_num

                # Determine which validations to run for this turn
                should_be_listening = turn_num <= tc.listening_meta.min_listening_turns
                if should_be_listening:
                    # Listening-specific validations
                    all_validations = get_listening_turn_validations() + turn.validations
                else:
                    # After min listening turns: standard checks only (phase can be anything)
                    all_validations = [
                        Validation("response_not_empty", description="Response is non-empty"),
                        Validation("no_markdown", description="No markdown formatting"),
                        Validation("no_hollow_phrases", description="No hollow/banned phrases"),
                        Validation("no_product_urls", description="No product URLs in text"),
                        Validation("max_words", {"n": 120}, "Response under 120 words"),
                    ] + turn.validations

                for v in all_validations:
                    vr = run_validation(v, tr.bot_response, data)
                    tr.validation_results.append(vr)
                    if vr["passed"]:
                        case_result.passed += 1
                    else:
                        case_result.failed += 1
                        if "error" in vr["detail"]:
                            case_result.errors += 1
                        print(f"      FAIL: {vr['description']} — {vr['detail']}")

            except Exception as e:
                tr.error = str(e)
                print(f"      EXCEPTION: {e}")
                case_result.errors += 1

            case_result.turn_results.append(tr)

            # Inter-turn delay
            if i < len(tc.turns) - 1:
                await asyncio.sleep(INTER_TURN_DELAY)

        # Check if min listening was met
        if case_result.first_guidance_turn > 0:
            case_result.min_listening_met = (
                case_result.first_guidance_turn > tc.listening_meta.min_listening_turns
            )
        else:
            # Never transitioned — that's fine for listening test
            case_result.min_listening_met = True

        total = case_result.passed + case_result.failed
        status = "PASS" if case_result.failed == 0 and case_result.errors == 0 else "FAIL"
        listen_status = "OK" if case_result.min_listening_met else "PREMATURE"
        print(f"\n  Result: {status} ({case_result.passed}/{total} checks, "
              f"first_guidance_turn={case_result.first_guidance_turn or 'never'}, "
              f"listen={listen_status})")

        return case_result

    async def run_all(
        self,
        cases: list[TestCase] | None = None,
    ) -> list[CaseResult]:
        """Run all (or selected) test cases."""
        target_cases = cases or ALL_TEST_CASES
        print(f"\n{'='*70}")
        print(f"  3ioNetra MITRA — Listening Phase Test Suite")
        print(f"  Target: {self.base_url}")
        print(f"  Cases: {len(target_cases)}")
        print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}")

        async with httpx.AsyncClient() as client:
            await self.authenticate(client)

            for tc in target_cases:
                result = await self.run_case(client, tc)
                self.results.append(result)
                await asyncio.sleep(1)  # brief pause between cases

        return self.results

    def generate_report(self) -> str:
        """Generate JSON + Markdown reports."""
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # ---- JSON output ----
        json_data = []
        for r in self.results:
            case_json = {
                "case_id": r.case_id,
                "category": r.category,
                "title": r.title,
                "min_listening_turns": r.listening_meta.min_listening_turns,
                "high_intensity": r.listening_meta.high_intensity,
                "first_guidance_turn": r.first_guidance_turn,
                "min_listening_met": r.min_listening_met,
                "passed": r.passed,
                "failed": r.failed,
                "errors": r.errors,
                "turns": [],
            }
            for tr in r.turn_results:
                case_json["turns"].append({
                    "turn_number": tr.turn_number,
                    "user_message": tr.user_message,
                    "bot_response": tr.bot_response,
                    "phase": tr.phase,
                    "signals": tr.signals,
                    "turn_count": tr.turn_count,
                    "recommended_products": tr.recommended_products,
                    "validation_results": tr.validation_results,
                    "error": tr.error,
                })
            json_data.append(case_json)

        json_path = RESULTS_DIR / "results.json"
        json_path.write_text(json.dumps(json_data, indent=2, ensure_ascii=False), encoding="utf-8")

        # ---- Markdown report ----
        total_passed = sum(r.passed for r in self.results)
        total_failed = sum(r.failed for r in self.results)
        total_errors = sum(r.errors for r in self.results)
        total_checks = total_passed + total_failed
        cases_passed = sum(1 for r in self.results if r.failed == 0 and r.errors == 0)
        cases_failed = len(self.results) - cases_passed
        premature_count = sum(1 for r in self.results if not r.min_listening_met)

        lines = [
            "# 3ioNetra Mitra — Listening Phase Test Report",
            "",
            f"**Run:** {now}",
            f"**Target:** `{self.base_url}`",
            f"**Total Cases:** {len(self.results)}",
            f"**Cases Passed:** {cases_passed} | **Cases Failed:** {cases_failed}",
            f"**Total Checks:** {total_checks} | **Passed:** {total_passed} | "
            f"**Failed:** {total_failed} | **Errors:** {total_errors}",
            f"**Pass Rate:** {total_passed / total_checks * 100:.1f}%" if total_checks > 0 else "**Pass Rate:** N/A",
            f"**Premature Transitions:** {premature_count} / {len(self.results)} cases",
            "",
            "---",
            "",
        ]

        # ---- Category breakdown ----
        lines.append("## Category Breakdown\n")
        lines.append("| Category | Cases | Phase Pass% | Format Pass% | Premature Transitions |")
        lines.append("|----------|-------|-------------|--------------|----------------------|")

        categories: dict[str, dict] = {}
        for r in self.results:
            cat = r.category
            if cat not in categories:
                categories[cat] = {
                    "cases": 0, "phase_pass": 0, "phase_total": 0,
                    "format_pass": 0, "format_total": 0, "premature": 0,
                }
            categories[cat]["cases"] += 1
            if not r.min_listening_met:
                categories[cat]["premature"] += 1

            for tr in r.turn_results:
                for vr in tr.validation_results:
                    desc = vr["description"].lower()
                    if "phase" in desc or "listening" in desc or "clarification" in desc:
                        categories[cat]["phase_total"] += 1
                        if vr["passed"]:
                            categories[cat]["phase_pass"] += 1
                    elif any(k in desc for k in ["markdown", "hollow", "url", "empty", "words"]):
                        categories[cat]["format_total"] += 1
                        if vr["passed"]:
                            categories[cat]["format_pass"] += 1

        cat_names = {
            "A": "A: Pure Emotional Venting",
            "B": "B: High-Intensity Emotions",
            "C": "C: Gradual Opening Up",
            "D": "D: Rhetorical Questions",
            "E": "E: Short/Vague Messages",
            "F": "F: Multi-Domain",
            "G": "G: Edge Cases",
        }

        for cat, stats in categories.items():
            phase_pct = f"{stats['phase_pass']/stats['phase_total']*100:.0f}%" if stats['phase_total'] > 0 else "N/A"
            format_pct = f"{stats['format_pass']/stats['format_total']*100:.0f}%" if stats['format_total'] > 0 else "N/A"
            label = cat_names.get(cat, cat)
            lines.append(
                f"| {label} | {stats['cases']} | {phase_pct} | {format_pct} | {stats['premature']} |"
            )

        lines.append("")
        lines.append("---")
        lines.append("")

        # ---- Premature Transition Failures ----
        premature_cases = [r for r in self.results if not r.min_listening_met]
        if premature_cases:
            lines.append("## Premature Transition Failures\n")
            lines.append("Cases where guidance was given before the required listening turns:\n")
            for r in premature_cases:
                intensity = "HIGH" if r.listening_meta.high_intensity else "normal"
                lines.append(
                    f"- **Case #{r.case_id}** ({r.title}): first guidance at turn "
                    f"{r.first_guidance_turn}, needed >{r.listening_meta.min_listening_turns} "
                    f"[{intensity}]"
                )
            lines.append("")
            lines.append("---")
            lines.append("")
        else:
            lines.append("## Premature Transition Failures\n")
            lines.append("None! All cases met minimum listening turn requirements.\n")
            lines.append("---")
            lines.append("")

        # ---- Format Violations ----
        format_failures = []
        for r in self.results:
            for tr in r.turn_results:
                for vr in tr.validation_results:
                    desc = vr["description"].lower()
                    if not vr["passed"] and any(k in desc for k in ["markdown", "hollow"]):
                        format_failures.append((r.case_id, r.title, tr.turn_number, vr["description"], vr["detail"]))

        if format_failures:
            lines.append("## Format Violations\n")
            for case_id, title, turn_num, desc, detail in format_failures:
                lines.append(f"- Case #{case_id} ({title}), Turn {turn_num}: {desc} — {detail}")
            lines.append("")
            lines.append("---")
            lines.append("")

        # ---- Content Violations ----
        content_failures = []
        for r in self.results:
            for tr in r.turn_results:
                for vr in tr.validation_results:
                    desc = vr["description"].lower()
                    if not vr["passed"] and any(k in desc for k in ["verse", "mantra", "scripture"]):
                        content_failures.append((r.case_id, r.title, tr.turn_number, vr["description"], vr["detail"]))

        if content_failures:
            lines.append("## Content Violations (Scripture in Listening)\n")
            for case_id, title, turn_num, desc, detail in content_failures:
                lines.append(f"- Case #{case_id} ({title}), Turn {turn_num}: {desc} — {detail}")
            lines.append("")
            lines.append("---")
            lines.append("")

        # ---- Per-case detail ----
        lines.append("## Detailed Results\n")

        current_category = ""
        for r in self.results:
            if r.category != current_category:
                current_category = r.category
                label = cat_names.get(current_category, current_category)
                lines.append(f"### {label}\n")

            status = "PASS" if r.failed == 0 and r.errors == 0 else "FAIL"
            listen_status = "OK" if r.min_listening_met else "PREMATURE"
            first_g = r.first_guidance_turn if r.first_guidance_turn > 0 else "never"
            lines.append(
                f"#### Case #{r.case_id}: {r.title} [{status}] "
                f"(first_guidance={first_g}, min_listen={listen_status})\n"
            )

            for tr in r.turn_results:
                lines.append(f"**Turn {tr.turn_number}**")
                lines.append(f"- **User:** {tr.user_message}")

                if tr.error:
                    lines.append(f"- **ERROR:** {tr.error}")
                else:
                    resp_display = tr.bot_response[:500]
                    if len(tr.bot_response) > 500:
                        resp_display += "..."
                    lines.append(f"- **Bot ({tr.phase}):** {resp_display}")
                    lines.append(f"- **Signals:** `{json.dumps(tr.signals)}`")

                    for vr in tr.validation_results:
                        icon = "PASS" if vr["passed"] else "FAIL"
                        lines.append(f"  - [{icon}] {vr['description']}: {vr['detail']}")

                lines.append("")

            lines.append("---\n")

        report = "\n".join(lines)
        md_path = RESULTS_DIR / "listening_phase_report.md"
        md_path.write_text(report, encoding="utf-8")

        print(f"\n{'='*70}")
        print(f"  Reports saved to:")
        print(f"    JSON: {json_path}")
        print(f"    MD:   {md_path}")
        print(f"  Total: {total_checks} checks | {total_passed} passed | {total_failed} failed | {total_errors} errors")
        print(f"  Cases: {cases_passed}/{len(self.results)} passed")
        print(f"  Premature transitions: {premature_count}")
        print(f"{'='*70}")
        return str(md_path)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="3ioNetra Mitra — Listening Phase Test Suite")
    parser.add_argument("--url", default=DEFAULT_BASE_URL, help="API base URL")
    parser.add_argument("--case", type=int, help="Run a single case by ID (1-54)")
    parser.add_argument("--category", type=str, help="Run all cases in a category (A-G)")
    args = parser.parse_args()

    runner = ListeningPhaseRunner(base_url=args.url)

    # Filter cases
    cases = ALL_TEST_CASES
    if args.case:
        cases = [tc for tc in ALL_TEST_CASES if tc.id == args.case]
        if not cases:
            print(f"Case #{args.case} not found. Valid IDs: 1-{len(ALL_TEST_CASES)}")
            sys.exit(1)
    elif args.category:
        cases = [tc for tc in ALL_TEST_CASES if args.category.upper() == tc.category.upper()]
        if not cases:
            cats = sorted(set(tc.category for tc in ALL_TEST_CASES))
            print(f"No cases match category '{args.category}'. Available: {cats}")
            sys.exit(1)

    # Run
    asyncio.run(runner.run_all(cases))

    # Generate report
    runner.generate_report()


if __name__ == "__main__":
    main()
