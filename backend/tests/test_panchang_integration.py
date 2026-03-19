"""
Panchang Integration Test Suite for 3ioNetra Mitra
====================================================
Validates that panchang (Hindu calendar) data flows correctly into companion
responses. Tests direct panchang queries, natural weaving in guidance,
special day awareness, and no-data-dump restraint.

Key design: Panchang changes daily, so validations are built dynamically
by first fetching GET /api/panchang/today and then checking:
  - If the LLM mentions a tithi/nakshatra, it must match the real one
  - Direct panchang queries must reference actual tithi/nakshatra
  - Panchang data must not be dumped as raw calendar readout
  - Emotional venting scenarios must not have intrusive panchang terms

Usage:
    python tests/test_panchang_integration.py
    python tests/test_panchang_integration.py --case 3
    python tests/test_panchang_integration.py --category A
    python tests/test_panchang_integration.py --url http://localhost:8080
"""

import asyncio
import httpx
import json
import re
import sys
import argparse
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DEFAULT_BASE_URL = "http://localhost:8080"
TEST_EMAIL = "test_panchang_eval@test.com"
TEST_PASSWORD = "TestPanchang2026!"
TEST_NAME = "Panchang Integration Evaluator"
RESULTS_DIR = Path(__file__).parent / "panchang_integration_results"
REQUEST_TIMEOUT = 90.0
INTER_TURN_DELAY = 2.0

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

# ---------------------------------------------------------------------------
# Complete tithi and nakshatra lists (for hallucination detection)
# ---------------------------------------------------------------------------
ALL_TITHIS = [
    "pratipada", "prathama", "dwitiya", "tritiya", "chaturthi", "panchami",
    "shashthi", "saptami", "ashtami", "navami", "dashami", "ekadashi",
    "dwadashi", "trayodashi", "chaturdashi", "purnima", "amavasya",
    # Hindi variants
    "pratham", "dooj", "teej", "chauth", "pancham", "chhath",
    "saptmi", "aathvi", "naumi", "dasmi",
]

ALL_NAKSHATRAS = [
    "ashwini", "bharani", "krittika", "rohini", "mrigashira", "mrigashirsha",
    "ardra", "punarvasu", "pushya", "ashlesha", "magha", "purva phalguni",
    "uttara phalguni", "hasta", "chitra", "swati", "vishakha", "anuradha",
    "jyeshtha", "moola", "mula", "purva ashadha", "uttara ashadha",
    "shravana", "dhanishta", "shatabhisha", "purva bhadrapada",
    "uttara bhadrapada", "revati",
]

# Five limbs of panchang — used to detect raw data dumps
PANCHANG_LIMBS = ["tithi", "nakshatra", "yoga", "karana", "vaara"]


# ---------------------------------------------------------------------------
# Panchang state (fetched at runtime)
# ---------------------------------------------------------------------------
@dataclass
class PanchangState:
    tithi: str = ""
    nakshatra: str = ""
    yoga: str = ""
    karana: str = ""
    vaara: str = ""
    special_info: str = ""
    is_special_day: bool = False
    raw: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Data classes (mirror test_listening_phase.py pattern)
# ---------------------------------------------------------------------------
@dataclass
class Validation:
    check_type: str
    params: dict = field(default_factory=dict)
    description: str = ""


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
    passed: int = 0
    failed: int = 0
    errors: int = 0
    error: str = ""


# ---------------------------------------------------------------------------
# Personas (reused from test_listening_phase.py)
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
def run_validation(v: Validation, response: str, api_data: dict, panchang: PanchangState) -> dict:
    """Run a single validation check. Returns {description, passed, detail}."""
    result = {"description": v.description or v.check_type, "passed": False, "detail": ""}

    try:
        if v.check_type == "response_not_empty":
            result["passed"] = len(response.strip()) > 0
            result["detail"] = f"{len(response)} chars"

        elif v.check_type == "max_words":
            limit = v.params["n"]
            word_count = len(response.split())
            result["passed"] = word_count <= limit
            result["detail"] = f"{word_count} words (limit {limit})"

        elif v.check_type == "must_contain_any":
            texts = [t.lower() for t in v.params["texts"]]
            found = [t for t in texts if t in response.lower()]
            result["passed"] = len(found) > 0
            result["detail"] = f"found: {found}" if found else f"none of {texts[:5]}..."

        elif v.check_type == "must_not_contain_any":
            texts = [t.lower() for t in v.params["texts"]]
            found = [t for t in texts if t in response.lower()]
            result["passed"] = len(found) == 0
            result["detail"] = f"unwanted found: {found}" if found else "clean"

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

        elif v.check_type == "no_product_urls":
            url_patterns = ["my3ionetra.com", "3ionetra.com/product", "http", "www."]
            found = [p for p in url_patterns if p in response.lower()]
            result["passed"] = len(found) == 0
            result["detail"] = f"found URLs: {found}" if found else "clean"

        # ----- Panchang-specific checks -----

        elif v.check_type == "panchang_reference":
            # Response must mention actual tithi OR nakshatra name
            resp_lower = response.lower()
            tithi_found = panchang.tithi and panchang.tithi.lower() in resp_lower
            nakshatra_found = panchang.nakshatra and panchang.nakshatra.lower() in resp_lower
            result["passed"] = tithi_found or nakshatra_found
            mentions = []
            if tithi_found:
                mentions.append(f"tithi '{panchang.tithi}'")
            if nakshatra_found:
                mentions.append(f"nakshatra '{panchang.nakshatra}'")
            result["detail"] = f"found: {', '.join(mentions)}" if mentions else (
                f"neither tithi '{panchang.tithi}' nor nakshatra '{panchang.nakshatra}' found"
            )

        elif v.check_type == "no_panchang_dump":
            # Fail if 3+ of the 5 limbs appear as raw terms
            resp_lower = response.lower()
            limbs_found = [limb for limb in PANCHANG_LIMBS if limb in resp_lower]
            result["passed"] = len(limbs_found) < 3
            result["detail"] = f"limbs mentioned: {limbs_found}" if limbs_found else "clean"

        elif v.check_type == "correct_panchang":
            # If ANY tithi name or nakshatra name from the complete lists appears,
            # it must match the actual current value. Catches hallucinated dates.
            resp_lower = response.lower()
            wrong = []

            # Check for wrong tithis
            actual_tithi_lower = panchang.tithi.lower() if panchang.tithi else ""
            for t in ALL_TITHIS:
                if t in resp_lower and t not in actual_tithi_lower:
                    # Make sure it's not a substring of the actual tithi
                    if actual_tithi_lower and t in actual_tithi_lower:
                        continue
                    wrong.append(f"tithi '{t}' (actual: '{panchang.tithi}')")

            # Check for wrong nakshatras
            actual_nak_lower = panchang.nakshatra.lower() if panchang.nakshatra else ""
            for n in ALL_NAKSHATRAS:
                if n in resp_lower and n not in actual_nak_lower:
                    if actual_nak_lower and n in actual_nak_lower:
                        continue
                    wrong.append(f"nakshatra '{n}' (actual: '{panchang.nakshatra}')")

            result["passed"] = len(wrong) == 0
            result["detail"] = f"WRONG: {wrong}" if wrong else "no hallucinated panchang values"

        else:
            result["detail"] = f"unknown check type: {v.check_type}"

    except Exception as e:
        result["detail"] = f"validation error: {e}"

    return result


# ---------------------------------------------------------------------------
# Standard validations applied to every turn
# ---------------------------------------------------------------------------
def get_standard_validations() -> list[Validation]:
    return [
        Validation("response_not_empty", description="Response is non-empty"),
        Validation("no_markdown", description="No markdown formatting"),
        Validation("no_hollow_phrases", description="No hollow/banned phrases"),
        Validation("no_product_urls", description="No product URLs in text"),
        Validation("max_words", {"n": 150}, "Response under 150 words"),
    ]


# ---------------------------------------------------------------------------
# Dynamic validation factories
# ---------------------------------------------------------------------------
def v_panchang_reference() -> Validation:
    return Validation("panchang_reference", description="Response mentions actual tithi or nakshatra")


def v_no_panchang_dump() -> Validation:
    return Validation("no_panchang_dump", description="No raw panchang data dump (3+ limbs)")


def v_correct_panchang() -> Validation:
    return Validation("correct_panchang", description="No hallucinated tithi/nakshatra values")


def v_phase_in(phases: list[str]) -> Validation:
    return Validation("phase_in", {"phases": phases}, f"Phase in {phases}")


def v_must_contain_any(texts: list[str], desc: str = "") -> Validation:
    return Validation("must_contain_any", {"texts": texts}, desc or f"Contains one of {texts[:3]}...")


def v_must_not_contain_any(texts: list[str], desc: str = "") -> Validation:
    return Validation("must_not_contain_any", {"texts": texts}, desc or f"Does not contain {texts[:3]}...")


# ---------------------------------------------------------------------------
# Build test cases dynamically based on panchang state
# ---------------------------------------------------------------------------
def build_test_cases(panchang: PanchangState) -> list[TestCase]:
    cases: list[TestCase] = []

    # =======================================================================
    # CATEGORY A: Direct Panchang Queries (3 cases)
    # =======================================================================

    # A1: "Aaj ka tithi kya hai?"
    cases.append(TestCase(
        id=1, category="A", title="Direct Tithi Query (Hindi)",
        persona=PERSONAS["arjun"],
        description="Directly asks about today's tithi and special days.",
        turns=[
            Turn("namaste"),
            Turn("aaj ka tithi kya hai?", [
                v_panchang_reference(),
                v_correct_panchang(),
                v_no_panchang_dump(),
            ]),
            Turn("aur koi special din hai aaj?", [
                v_correct_panchang(),
                v_no_panchang_dump(),
            ]),
        ],
    ))

    # A2: "Tell me about today's nakshatra"
    cases.append(TestCase(
        id=2, category="A", title="Direct Nakshatra Query",
        persona=PERSONAS["meera"],
        description="Asks about nakshatra and what puja to do.",
        turns=[
            Turn("namaste"),
            Turn("aaj ka nakshatra kya hai? kya puja karni chahiye?", [
                v_panchang_reference(),
                v_correct_panchang(),
                v_no_panchang_dump(),
            ]),
            Turn("is nakshatra mein kya karna shubh hai?", [
                v_correct_panchang(),
                v_no_panchang_dump(),
            ]),
        ],
    ))

    # A3: "Is today shubh for starting meditation?"
    cases.append(TestCase(
        id=3, category="A", title="Auspiciousness Query for Meditation",
        persona=PERSONAS["ananya"],
        description="Asks if today is auspicious for starting meditation.",
        turns=[
            Turn("hii"),
            Turn("main meditation start karna chahti hoon. kya aaj ka din shubh hai?", [
                v_correct_panchang(),
                v_no_panchang_dump(),
            ]),
            Turn("kitne baje karna chahiye?", [
                v_correct_panchang(),
                v_no_panchang_dump(),
            ]),
        ],
    ))

    # =======================================================================
    # CATEGORY B: Natural Weaving in Guidance (3 cases)
    # =======================================================================

    # B1: Career guidance
    cases.append(TestCase(
        id=4, category="B", title="Career Guidance — Natural Panchang Weaving",
        persona=PERSONAS["arjun"],
        description="Career concern leading to guidance. Panchang may appear naturally but must be accurate.",
        turns=[
            Turn("namaste"),
            Turn("job change karna hai but bahut confused hoon"),
            Turn("2 saal se growth nahi ho rahi. manager bhi supportive nahi hai"),
            Turn("koi practice batao jo clarity de sake", [
                v_correct_panchang(),
                v_no_panchang_dump(),
            ]),
        ],
    ))

    # B2: Family tension
    cases.append(TestCase(
        id=5, category="B", title="Family Tension — Natural Panchang Weaving",
        persona=PERSONAS["meera"],
        description="Family conflict leading to guidance. Panchang if woven must be correct.",
        turns=[
            Turn("namaste"),
            Turn("ghar mein bahut tension hai. pati se baat nahi ho rahi"),
            Turn("lagta hai sab toot raha hai. bachche bhi pareshaan hain"),
            Turn("kuch upay batao na. kya karu?", [
                v_correct_panchang(),
                v_no_panchang_dump(),
            ]),
        ],
    ))

    # B3: Spiritual growth
    cases.append(TestCase(
        id=6, category="B", title="Spiritual Growth — Natural Panchang Weaving",
        persona=PERSONAS["vikram"],
        description="Retirement spiritual path. Panchang may enrich the guidance.",
        turns=[
            Turn("pranam"),
            Turn("retirement ke baad spiritual path pe aana chahta hoon"),
            Turn("pehle bahut pooja karta tha. ab phir se shuru karna hai"),
            Turn("koi mantra suggest karo jo daily kar sakun", [
                v_correct_panchang(),
                v_no_panchang_dump(),
            ]),
        ],
    ))

    # =======================================================================
    # CATEGORY C: Special Day Awareness (2 cases)
    # =======================================================================

    # Build conditional validations based on actual panchang state
    special_day_keywords = [
        "ekadashi", "amavasya", "purnima", "vrat", "upvas",
        "fasting", "special", "vishesh", "shubh",
    ]

    # C1: "Aaj kuch vishesh hai kya?"
    turn2_validations_c1 = [v_correct_panchang(), v_no_panchang_dump()]
    if panchang.is_special_day:
        turn2_validations_c1.append(
            v_must_contain_any(special_day_keywords, "Special day acknowledged")
        )

    cases.append(TestCase(
        id=7, category="C", title="Special Day Inquiry",
        persona=PERSONAS["meera"],
        description=f"Asks if today is special. is_special_day={panchang.is_special_day}",
        turns=[
            Turn("namaste"),
            Turn("aaj kuch vishesh hai kya? koi vrat ya pooja karni chahiye?", turn2_validations_c1),
            Turn("acha, aur kya karna chahiye aaj?", [
                v_correct_panchang(),
                v_no_panchang_dump(),
            ]),
        ],
    ))

    # C2: "Kab shuru karu naya practice?"
    turn2_validations_c2 = [v_correct_panchang(), v_no_panchang_dump()]

    cases.append(TestCase(
        id=8, category="C", title="Timing Inquiry for New Practice",
        persona=PERSONAS["arjun"],
        description="Asks when to start a new practice. Panchang may be used as timing anchor.",
        turns=[
            Turn("namaste"),
            Turn("koi naya practice start karna chahta hoon. kab shuru karu?", turn2_validations_c2),
            Turn("acha, aur koi mantra bhi batao", [
                v_correct_panchang(),
                v_no_panchang_dump(),
            ]),
        ],
    ))

    # =======================================================================
    # CATEGORY D: No-Data-Dump / Restraint (2 cases)
    # =======================================================================

    raw_panchang_terms = ["yoga:", "karana:", "vaara:", "tithi:", "nakshatra:"]

    # D1: Friendship breakdown — panchang should not intrude
    cases.append(TestCase(
        id=9, category="D", title="Friendship Breakdown — No Panchang Intrusion",
        persona=PERSONAS["arjun"],
        description="Pure emotional venting about friendship loss. Panchang must not intrude.",
        turns=[
            Turn("hey"),
            Turn("best friend ne baat karna band kar diya", [
                v_no_panchang_dump(),
            ]),
            Turn("15 saal ki dosti thi. ek din achanak sab khatam", [
                v_no_panchang_dump(),
            ]),
            Turn("bahut akela feel ho raha hai", [
                v_no_panchang_dump(),
                v_must_not_contain_any(raw_panchang_terms, "No raw panchang terms in emotional response"),
            ]),
        ],
    ))

    # D2: Spousal bereavement — panchang absolutely must not intrude
    cases.append(TestCase(
        id=10, category="D", title="Spousal Bereavement — No Panchang Intrusion",
        persona=PERSONAS["vikram"],
        description="Deep grief after spouse's death. Panchang must not appear at all.",
        turns=[
            Turn("pranam"),
            Turn("patni ka dehant ho gaya", [
                v_no_panchang_dump(),
            ]),
            Turn("40 saal ka saath tha. ab ghar soona lag raha hai", [
                v_no_panchang_dump(),
            ]),
            Turn("ghar mein sannata hai. kisi se baat karne ka mann nahi", [
                v_no_panchang_dump(),
                v_must_not_contain_any(raw_panchang_terms, "No raw panchang terms in grief response"),
            ]),
        ],
    ))

    return cases


# ---------------------------------------------------------------------------
# Runner class
# ---------------------------------------------------------------------------
class PanchangIntegrationRunner:
    def __init__(self, base_url: str = DEFAULT_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.token: str | None = None
        self.results: list[CaseResult] = []
        self.panchang: PanchangState = PanchangState()

    async def fetch_panchang(self, client: httpx.AsyncClient) -> bool:
        """Fetch current panchang state from the API."""
        print(f"\n{'='*70}")
        print(f"  Fetching current panchang from {self.base_url}/api/panchang/today")
        print(f"{'='*70}")

        try:
            resp = await client.get(
                f"{self.base_url}/api/panchang/today",
                timeout=30.0,
            )
            if resp.status_code != 200:
                print(f"  WARNING: Panchang API returned {resp.status_code}: {resp.text[:200]}")
                print(f"  Tests will proceed but panchang_reference checks may fail.")
                return False

            data = resp.json()
            self.panchang = PanchangState(
                tithi=data.get("tithi", ""),
                nakshatra=data.get("nakshatra", ""),
                yoga=data.get("yoga", ""),
                karana=data.get("karana", ""),
                vaara=data.get("vaara", ""),
                special_info=data.get("special_info", ""),
                is_special_day=bool(data.get("special_info", "").strip()),
                raw=data,
            )

            print(f"  Tithi:      {self.panchang.tithi}")
            print(f"  Nakshatra:  {self.panchang.nakshatra}")
            print(f"  Yoga:       {self.panchang.yoga}")
            print(f"  Karana:     {self.panchang.karana}")
            print(f"  Vaara:      {self.panchang.vaara}")
            print(f"  Special:    {self.panchang.special_info or '(none)'}")
            print(f"  Is Special: {self.panchang.is_special_day}")
            return True

        except Exception as e:
            print(f"  ERROR fetching panchang: {e}")
            print(f"  Tests will proceed but panchang_reference checks may fail.")
            return False

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

        # Try login again
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
        print(f"  Category: {tc.category} | Persona: {tc.persona['name']}")
        print(f"{'─'*70}")

        case_result = CaseResult(
            case_id=tc.id,
            category=tc.category,
            title=tc.title,
            turn_results=[],
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

                # Console preview
                preview = tr.bot_response[:120].replace("\n", " ")
                print(f"      Bot ({tr.phase}): {preview}...")

                # Run standard + turn-specific validations
                all_validations = get_standard_validations() + turn.validations

                for v in all_validations:
                    vr = run_validation(v, tr.bot_response, data, self.panchang)
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

        total = case_result.passed + case_result.failed
        status = "PASS" if case_result.failed == 0 and case_result.errors == 0 else "FAIL"
        print(f"\n  Result: {status} ({case_result.passed}/{total} checks)")

        return case_result

    async def run_all(
        self,
        case_id: Optional[int] = None,
        category: Optional[str] = None,
    ) -> list[CaseResult]:
        """Run all (or filtered) test cases."""
        print(f"\n{'='*70}")
        print(f"  3ioNetra MITRA — Panchang Integration Test Suite")
        print(f"  Target: {self.base_url}")
        print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}")

        async with httpx.AsyncClient() as client:
            # Step 1: Fetch panchang state
            await self.fetch_panchang(client)

            # Step 2: Authenticate
            await self.authenticate(client)

            # Step 3: Build test cases dynamically
            all_cases = build_test_cases(self.panchang)

            # Step 4: Filter
            target_cases = all_cases
            if case_id is not None:
                target_cases = [tc for tc in all_cases if tc.id == case_id]
                if not target_cases:
                    print(f"Case #{case_id} not found. Valid IDs: 1-{len(all_cases)}")
                    sys.exit(1)
            elif category is not None:
                target_cases = [tc for tc in all_cases if category.upper() == tc.category.upper()]
                if not target_cases:
                    cats = sorted(set(tc.category for tc in all_cases))
                    print(f"No cases match category '{category}'. Available: {cats}")
                    sys.exit(1)

            print(f"\n  Cases to run: {len(target_cases)}")

            # Step 5: Run cases
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
        json_data = {
            "run_at": now,
            "base_url": self.base_url,
            "panchang_state": {
                "tithi": self.panchang.tithi,
                "nakshatra": self.panchang.nakshatra,
                "yoga": self.panchang.yoga,
                "karana": self.panchang.karana,
                "vaara": self.panchang.vaara,
                "special_info": self.panchang.special_info,
                "is_special_day": self.panchang.is_special_day,
            },
            "cases": [],
        }

        for r in self.results:
            case_json = {
                "case_id": r.case_id,
                "category": r.category,
                "title": r.title,
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
            json_data["cases"].append(case_json)

        json_path = RESULTS_DIR / "results.json"
        json_path.write_text(json.dumps(json_data, indent=2, ensure_ascii=False), encoding="utf-8")

        # ---- Markdown report ----
        total_passed = sum(r.passed for r in self.results)
        total_failed = sum(r.failed for r in self.results)
        total_errors = sum(r.errors for r in self.results)
        total_checks = total_passed + total_failed
        cases_passed = sum(1 for r in self.results if r.failed == 0 and r.errors == 0)
        cases_failed = len(self.results) - cases_passed

        lines = [
            "# 3ioNetra Mitra — Panchang Integration Test Report",
            "",
            f"**Run:** {now}",
            f"**Target:** `{self.base_url}`",
            f"**Total Cases:** {len(self.results)}",
            f"**Cases Passed:** {cases_passed} | **Cases Failed:** {cases_failed}",
            f"**Total Checks:** {total_checks} | **Passed:** {total_passed} | "
            f"**Failed:** {total_failed} | **Errors:** {total_errors}",
            f"**Pass Rate:** {total_passed / total_checks * 100:.1f}%" if total_checks > 0 else "**Pass Rate:** N/A",
            "",
            "---",
            "",
            "## Current Panchang State",
            "",
            f"| Field | Value |",
            f"|-------|-------|",
            f"| Tithi | {self.panchang.tithi} |",
            f"| Nakshatra | {self.panchang.nakshatra} |",
            f"| Yoga | {self.panchang.yoga} |",
            f"| Karana | {self.panchang.karana} |",
            f"| Vaara | {self.panchang.vaara} |",
            f"| Special Day | {self.panchang.special_info or '(none)'} |",
            f"| Is Special | {self.panchang.is_special_day} |",
            "",
            "---",
            "",
        ]

        # ---- Category breakdown ----
        cat_names = {
            "A": "A: Direct Panchang Queries",
            "B": "B: Natural Weaving in Guidance",
            "C": "C: Special Day Awareness",
            "D": "D: No-Data-Dump / Restraint",
        }

        lines.append("## Category Breakdown\n")
        lines.append("| Category | Cases | Panchang Checks | Pass% |")
        lines.append("|----------|-------|-----------------|-------|")

        categories: dict[str, dict] = {}
        for r in self.results:
            cat = r.category
            if cat not in categories:
                categories[cat] = {"cases": 0, "panchang_pass": 0, "panchang_total": 0}
            categories[cat]["cases"] += 1

            for tr in r.turn_results:
                for vr in tr.validation_results:
                    desc = vr["description"].lower()
                    if any(k in desc for k in ["panchang", "tithi", "nakshatra", "hallucinated"]):
                        categories[cat]["panchang_total"] += 1
                        if vr["passed"]:
                            categories[cat]["panchang_pass"] += 1

        for cat, stats in sorted(categories.items()):
            label = cat_names.get(cat, cat)
            pct = f"{stats['panchang_pass']/stats['panchang_total']*100:.0f}%" if stats['panchang_total'] > 0 else "N/A"
            lines.append(f"| {label} | {stats['cases']} | {stats['panchang_pass']}/{stats['panchang_total']} | {pct} |")

        lines.append("")
        lines.append("---")
        lines.append("")

        # ---- Panchang Accuracy Failures ----
        accuracy_failures = []
        for r in self.results:
            for tr in r.turn_results:
                for vr in tr.validation_results:
                    if not vr["passed"] and "correct_panchang" in vr["description"].lower():
                        accuracy_failures.append(
                            (r.case_id, r.title, tr.turn_number, vr["detail"])
                        )

        lines.append("## Panchang Accuracy Failures\n")
        if accuracy_failures:
            lines.append("Cases where the LLM mentioned a wrong tithi or nakshatra:\n")
            for case_id, title, turn_num, detail in accuracy_failures:
                lines.append(f"- **Case #{case_id}** ({title}), Turn {turn_num}: {detail}")
        else:
            lines.append("None! No hallucinated panchang values detected.")
        lines.append("")
        lines.append("---")
        lines.append("")

        # ---- Data Dump Violations ----
        dump_failures = []
        for r in self.results:
            for tr in r.turn_results:
                for vr in tr.validation_results:
                    if not vr["passed"] and "dump" in vr["description"].lower():
                        dump_failures.append(
                            (r.case_id, r.title, tr.turn_number, vr["detail"])
                        )

        lines.append("## Data Dump Violations\n")
        if dump_failures:
            lines.append("Cases where 3+ panchang limbs were dumped as raw data:\n")
            for case_id, title, turn_num, detail in dump_failures:
                lines.append(f"- **Case #{case_id}** ({title}), Turn {turn_num}: {detail}")
        else:
            lines.append("None! No raw panchang data dumps detected.")
        lines.append("")
        lines.append("---")
        lines.append("")

        # ---- Detailed per-case results ----
        lines.append("## Detailed Results\n")

        current_category = ""
        for r in self.results:
            if r.category != current_category:
                current_category = r.category
                label = cat_names.get(current_category, current_category)
                lines.append(f"### {label}\n")

            status = "PASS" if r.failed == 0 and r.errors == 0 else "FAIL"
            lines.append(f"#### Case #{r.case_id}: {r.title} [{status}]\n")

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
        md_path = RESULTS_DIR / "panchang_integration_report.md"
        md_path.write_text(report, encoding="utf-8")

        print(f"\n{'='*70}")
        print(f"  Reports saved to:")
        print(f"    JSON: {json_path}")
        print(f"    MD:   {md_path}")
        print(f"  Panchang: {self.panchang.tithi} / {self.panchang.nakshatra}")
        print(f"  Total: {total_checks} checks | {total_passed} passed | {total_failed} failed | {total_errors} errors")
        print(f"  Cases: {cases_passed}/{len(self.results)} passed")
        print(f"{'='*70}")
        return str(md_path)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="3ioNetra Mitra — Panchang Integration Test Suite")
    parser.add_argument("--url", default=DEFAULT_BASE_URL, help="API base URL")
    parser.add_argument("--case", type=int, help="Run a single case by ID (1-10)")
    parser.add_argument("--category", type=str, help="Run all cases in a category (A-D)")
    args = parser.parse_args()

    runner = PanchangIntegrationRunner(base_url=args.url)
    asyncio.run(runner.run_all(case_id=args.case, category=args.category))
    runner.generate_report()


if __name__ == "__main__":
    main()
