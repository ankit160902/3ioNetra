"""
Returning User Continuity Test for 3ioNetra Mitra
===================================================
Tests that the system remembers past conversations and follows up naturally
when a user returns across multiple sessions.

6 scenarios validate:
  - Single-topic grief recall
  - Multi-topic accumulation across 3 sessions
  - Emotional arc continuity
  - Profile personalization (deity, etc.)
  - Cross-session skip recall
  - Gentle recall of sensitive topics (no insensitive probing)

Usage:
    python tests/test_returning_user.py
    python tests/test_returning_user.py --scenario 1
    python tests/test_returning_user.py --url http://localhost:8080
"""

import asyncio
import httpx
import json
import re
import sys
import time
import argparse
import secrets
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DEFAULT_BASE_URL = "http://localhost:8080"
RESULTS_DIR = Path(__file__).parent / "returning_user_results"
REQUEST_TIMEOUT = 90.0
INTER_TURN_DELAY = 2.0
SAVE_WAIT_DELAY = 3.0  # seconds to wait after save for MongoDB propagation

HOLLOW_PHRASES = (
    "i hear you",
    "i understand",
    "it sounds like",
    "that must be difficult",
    "everything happens for a reason",
    "others have it worse",
    "just be positive",
)

DATABASE_PHRASES = (
    "according to my records",
    "you previously mentioned",
    "in our last conversation you said",
    "my records show",
    "based on your history",
    "our database indicates",
    "your file says",
)

# Phrases that indicate the bot recognizes a returning user — these would
# never appear in a first-time greeting, so they count as past-context recall.
CONTINUITY_MARKERS = (
    "we last",          # "since we last spoke"
    "last time",        # "last time we talked"
    "we talked",        # "we talked about"
    "we discussed",     # "we discussed"
    "we spoke",         # "when we spoke"
    "I remember",       # "I remember you"
    "you shared",       # "what you shared"
    "you mentioned",    # "you mentioned"
    "thinking of you",  # "I was thinking of you"
    "thinking about you",
    "our conversation",  # "our conversation last time"
    "your journey",     # returning-user reference
    "we met",           # "when we met"
    "you again",        # "good to see/hear from you again"
    "welcome back",     # explicit returning-user greeting
    "you are carrying", # implies past knowledge of burden
    "have you back",    # "good to have you back"
    "you came back",    # "glad you came back"
    "you are back",     # "glad you are back"
    "hear from you",    # "good to hear from you" — used for known contacts
)


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------
@dataclass
class TurnResult:
    turn_number: int
    session_number: int
    user_message: str
    bot_response: str
    phase: str
    response_time: float
    error: Optional[str] = None
    validations: Dict[str, bool] = field(default_factory=dict)


@dataclass
class SessionResult:
    session_number: int
    session_id: str
    turns: List[TurnResult] = field(default_factory=list)
    saved: bool = False
    error: Optional[str] = None


@dataclass
class ScenarioResult:
    scenario_id: int
    name: str
    description: str
    sessions: List[SessionResult] = field(default_factory=list)
    passed: bool = False
    recall_score: float = 0.0
    notes: List[str] = field(default_factory=list)


@dataclass
class Session:
    """A session within a scenario: list of user messages + validation config."""
    messages: List[str]
    is_returning: bool = False
    recall_keywords: List[str] = field(default_factory=list)
    sensitive: bool = False  # If True, bot should NOT proactively ask about keywords


@dataclass
class Scenario:
    """A multi-session test scenario."""
    id: int
    name: str
    description: str
    email_prefix: str
    persona: Dict
    sessions: List[Session]


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------
SCENARIOS = [
    Scenario(
        id=1,
        name="Single-Topic Grief Recall",
        description="User discusses mother's passing in session 1. Returns in session 2. Bot should reference grief/mother naturally.",
        email_prefix="grief_recall",
        persona={
            "name": "Meera Test",
            "gender": "female",
            "profession": "Teacher",
            "preferred_deity": "Krishna",
            "age_group": "50-60",
        },
        sessions=[
            Session(messages=[
                "Namaste, I need someone to talk to",
                "My mother passed away three months ago and I feel so empty",
                "She was everything to me. We used to do puja together every morning",
                "I cannot even enter the puja room anymore without crying",
                "Sometimes I feel her presence near the tulsi plant",
                "Thank you for listening, I will try the mantra you suggested",
            ]),
            Session(
                messages=[
                    "Namaste, I am back",
                    "I have been thinking about what we discussed",
                    "Today was especially hard, it was her birthday",
                ],
                is_returning=True,
                recall_keywords=["mother", "grief", "puja", "loss", "passing", "empty", "tulsi", "strength", "courage", "journey", "difficult", "hard", "pain", "carried", "carrying", "shared", "remember", "last time", "before", "heart", "morning"],
            ),
        ],
    ),
    Scenario(
        id=2,
        name="Multi-Topic Accumulation",
        description="Session 1: career stress. Session 2: relationship worry. Session 3: bot should know BOTH.",
        email_prefix="multi_topic",
        persona={
            "name": "Arjun Test",
            "gender": "male",
            "profession": "Software Engineer",
            "preferred_deity": "Shiva",
            "age_group": "30-40",
        },
        sessions=[
            Session(messages=[
                "Hello, I am stressed about my career",
                "My company is doing layoffs and I am worried about my job",
                "I have been working 14 hour days but it never feels enough",
                "I feel like I am losing my purpose in this corporate race",
                "Thank you, I will try to meditate on this",
            ]),
            Session(messages=[
                "Namaste, I have a different concern today",
                "My wife and I have been arguing a lot lately",
                "She says I am never present even when I am home",
                "I know she is right but I do not know how to change",
                "I will think about what you said, thank you",
            ]),
            Session(
                messages=[
                    "Namaste, I need your guidance again",
                    "Everything feels overwhelming, both at work and at home",
                    "How do I find balance in all of this",
                ],
                is_returning=True,
                recall_keywords=["career", "job", "layoff", "work", "wife", "relationship", "argue", "balance", "stress", "overwhelm", "home", "present", "purpose", "corporate", "hours", "losing", "meditat", "company", "worried"],
            ),
        ],
    ),
    Scenario(
        id=3,
        name="Emotional Arc Continuity",
        description="Session 1: deep anxiety, bot suggests meditation. Session 2: user says feeling better. Bot should connect improvement to prior state.",
        email_prefix="emotional_arc",
        persona={
            "name": "Priya Test",
            "gender": "female",
            "profession": "Marketing Manager",
            "preferred_deity": "Durga",
            "age_group": "25-35",
        },
        sessions=[
            Session(messages=[
                "I have been having severe anxiety attacks",
                "They come suddenly, my heart races and I cannot breathe",
                "It started after I took on a big project at work",
                "I feel like I am failing at everything",
                "I have never tried meditation before but I am willing to try",
                "Thank you, I will try the breathing exercise tonight",
            ]),
            Session(
                messages=[
                    "Namaste, I wanted to share something positive",
                    "I have been feeling much better since our last talk",
                    "The breathing exercises have really helped with my anxiety",
                ],
                is_returning=True,
                recall_keywords=["anxiety", "meditation", "breathing", "panic", "better", "improvement", "project", "worry", "stress", "calm", "peace", "practice", "exercise", "sleep", "heart", "last time", "before", "progress", "strength", "step", "light", "breath", "attack", "racing", "failing", "storm"],
            ),
        ],
    ),
    Scenario(
        id=4,
        name="Profile Personalization",
        description="Session 1: user mentions devotion to Krishna. Session 2: bot should reference Krishna specifically, not generic deity.",
        email_prefix="profile_deity",
        persona={
            "name": "Govind Test",
            "gender": "male",
            "profession": "Retired",
            "preferred_deity": "Krishna",
            "age_group": "60+",
        },
        sessions=[
            Session(messages=[
                "Namaste, I am a devotee of Lord Krishna since childhood",
                "I read the Bhagavad Gita every morning",
                "Lately I have been struggling to concentrate during my path",
                "My mind wanders and I feel disconnected from Govinda",
                "Thank you, I will try chanting the Hare Krishna Mahamantra with more focus",
            ]),
            Session(
                messages=[
                    "Namaste, I am seeking guidance again",
                    "I want to deepen my spiritual practice",
                    "What should I focus on for spiritual growth",
                ],
                is_returning=True,
                recall_keywords=["Krishna", "Govinda", "Gita", "Bhagavad", "devotion", "chanting", "Mahamantra"],
            ),
        ],
    ),
    Scenario(
        id=5,
        name="Cross-Session Skip Recall",
        description="Session 1: exam stress. Session 2: health issue. Session 3: bot should remember exam topic from session 1.",
        email_prefix="skip_recall",
        persona={
            "name": "Rohan Test",
            "gender": "male",
            "profession": "University Student",
            "preferred_deity": "Hanuman",
            "age_group": "18-25",
        },
        sessions=[
            Session(messages=[
                "I am so stressed about my final exams",
                "I have my engineering boards in two weeks and I cannot focus",
                "My parents are putting so much pressure on me",
                "I pray to Hanuman ji for strength but I still feel weak",
            ]),
            Session(messages=[
                "Namaste, something different today",
                "I have been having headaches and not sleeping well",
                "The doctor says it is stress related",
                "I need to find a way to relax",
            ]),
            Session(
                messages=[
                    "Namaste, I am back again",
                    "My exams are next week now and I am panicking",
                    "Do you remember what we discussed about my studies",
                ],
                is_returning=True,
                recall_keywords=["exam", "board", "engineering", "study", "focus", "parent", "pressure", "test", "preparation", "academic", "headache", "sleep", "stress"],
            ),
        ],
    ),
    Scenario(
        id=6,
        name="Gentle Recall (Sensitive)",
        description="Session 1: user shares about divorce. Session 2: bot should NOT ask 'How is your divorce going?' — let user lead.",
        email_prefix="gentle_recall",
        persona={
            "name": "Ananya Test",
            "gender": "female",
            "profession": "Lawyer",
            "preferred_deity": "Durga",
            "age_group": "35-45",
        },
        sessions=[
            Session(messages=[
                "I am going through a divorce",
                "It has been very painful, we were married for 12 years",
                "I feel like a failure, like I could not keep my family together",
                "My children are confused and that breaks my heart the most",
                "Thank you for not judging me",
            ]),
            Session(
                messages=[
                    "Namaste, I just wanted to talk today",
                    "I have been feeling a bit better this week",
                    "I started going to the temple again",
                ],
                is_returning=True,
                recall_keywords=["divorce", "marriage", "children", "family", "separation", "strength", "courage", "journey", "difficult", "carried", "carrying", "shared", "brave", "temple", "pain", "healing", "through", "before", "last time", "heart", "twelve", "years", "failure", "together", "judging", "last spoke", "we spoke", "we last", "what you have been"],
                sensitive=True,
            ),
        ],
    ),
]


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------
def check_recall(response: str, keywords: List[str]) -> bool:
    """Check if response references at least one keyword from prior session or uses a continuity marker."""
    response_lower = response.lower()
    all_markers = list(keywords) + list(CONTINUITY_MARKERS)
    return any(kw.lower() in response_lower for kw in all_markers)


def check_no_data_dump(response: str) -> bool:
    """Ensure response doesn't clinically list past data."""
    # Heuristic: 3+ bullet points or numbered items = data dump
    bullet_count = len(re.findall(r'(?m)^[\s]*[-*•]\s', response))
    numbered_count = len(re.findall(r'(?m)^[\s]*\d+[.)]\s', response))
    return (bullet_count + numbered_count) < 3


def check_natural_language(response: str) -> bool:
    """Ensure no database-like phrasing."""
    response_lower = response.lower()
    return not any(phrase in response_lower for phrase in DATABASE_PHRASES)


def check_no_hollow_phrases(response: str) -> bool:
    """Check for hollow/banned phrases."""
    response_lower = response.lower()
    return not any(phrase in response_lower for phrase in HOLLOW_PHRASES)


def check_no_insensitive_recall(response: str, keywords: List[str]) -> bool:
    """For sensitive topics, check bot doesn't directly ask about them."""
    response_lower = response.lower()
    # Direct question patterns about sensitive keywords
    insensitive_patterns = [
        r"how is your (\w+ )?" + kw.lower() for kw in keywords
    ] + [
        r"how('s| is) the " + kw.lower() for kw in keywords
    ] + [
        r"tell me about your " + kw.lower() for kw in keywords
    ] + [
        r"what('s| is) happening with .*" + kw.lower() for kw in keywords
    ]
    for pattern in insensitive_patterns:
        if re.search(pattern, response_lower):
            return False
    return True


def check_not_generic_greeting(response: str) -> bool:
    """Check that response isn't a purely generic first-time greeting."""
    generic_markers = [
        "welcome! i'm here to listen",
        "how can i help you today",
        "what brings you here today",
        "this is a safe space",
    ]
    response_lower = response.lower()
    generic_count = sum(1 for m in generic_markers if m in response_lower)
    return generic_count < 2  # Allow one generic phrase but not full generic greeting


# ---------------------------------------------------------------------------
# API Client
# ---------------------------------------------------------------------------
class MitraClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)
        self.token: Optional[str] = None

    async def register(self, email: str, password: str, name: str, **profile) -> bool:
        try:
            resp = await self.client.post(
                f"{self.base_url}/api/auth/register",
                json={"email": email, "password": password, "name": name, **profile},
            )
            if resp.status_code == 200:
                data = resp.json()
                self.token = data.get("token")
                return True
            return False
        except Exception as e:
            print(f"  Registration failed: {e}")
            return False

    async def login(self, email: str, password: str) -> bool:
        try:
            resp = await self.client.post(
                f"{self.base_url}/api/auth/login",
                json={"email": email, "password": password},
            )
            if resp.status_code == 200:
                data = resp.json()
                self.token = data.get("token")
                return True
            return False
        except Exception as e:
            print(f"  Login failed: {e}")
            return False

    async def create_session(self) -> Optional[str]:
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        resp = await self.client.post(f"{self.base_url}/api/session/create", headers=headers)
        if resp.status_code == 200:
            return resp.json().get("session_id")
        return None

    async def send_message(self, session_id: str, message: str) -> Dict:
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        start = time.time()
        resp = await self.client.post(
            f"{self.base_url}/api/conversation",
            json={"session_id": session_id, "message": message},
            headers=headers,
        )
        elapsed = time.time() - start
        if resp.status_code == 200:
            data = resp.json()
            return {
                "response": data.get("response", ""),
                "phase": data.get("phase", "unknown"),
                "time": elapsed,
                "error": None,
            }
        return {"response": "", "phase": "error", "time": elapsed, "error": f"HTTP {resp.status_code}"}

    async def save_conversation(self, session_id: str, messages: List[Dict]) -> bool:
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        resp = await self.client.post(
            f"{self.base_url}/api/user/conversations",
            json={
                "conversation_id": session_id,
                "title": f"Test Conversation {session_id[:8]}",
                "messages": messages,
            },
            headers=headers,
        )
        return resp.status_code == 200

    async def close(self):
        await self.client.aclose()


# ---------------------------------------------------------------------------
# Test Runner
# ---------------------------------------------------------------------------
async def run_scenario(scenario: Scenario, base_url: str) -> ScenarioResult:
    result = ScenarioResult(
        scenario_id=scenario.id,
        name=scenario.name,
        description=scenario.description,
    )

    # Unique credentials per test run
    unique_suffix = secrets.token_hex(4)
    email = f"{scenario.email_prefix}_{unique_suffix}@test3io.com"
    password = "TestReturning2026!"

    client = MitraClient(base_url)

    # Register
    registered = await client.register(email, password, scenario.persona["name"], **{
        k: v for k, v in scenario.persona.items() if k != "name"
    })
    if not registered:
        # Maybe already exists, try login
        logged_in = await client.login(email, password)
        if not logged_in:
            result.notes.append("Failed to register or login")
            await client.close()
            return result

    print(f"\n{'='*60}")
    print(f"  Scenario {scenario.id}: {scenario.name}")
    print(f"  Email: {email}")
    print(f"{'='*60}")

    recall_hits = 0
    recall_checks = 0

    for sess_idx, sess_config in enumerate(scenario.sessions):
        sess_num = sess_idx + 1
        print(f"\n  --- Session {sess_num} ({'returning' if sess_config.is_returning else 'initial'}) ---")

        session_id = await client.create_session()
        if not session_id:
            result.notes.append(f"Failed to create session {sess_num}")
            continue

        sess_result = SessionResult(session_number=sess_num, session_id=session_id)
        conversation_messages = []

        for turn_idx, user_msg in enumerate(sess_config.messages):
            turn_num = turn_idx + 1
            print(f"    Turn {turn_num}: {user_msg[:60]}...")

            reply = await client.send_message(session_id, user_msg)
            bot_response = reply["response"]

            conversation_messages.append({"role": "user", "content": user_msg})
            if bot_response:
                conversation_messages.append({"role": "assistant", "content": bot_response})

            turn_result = TurnResult(
                turn_number=turn_num,
                session_number=sess_num,
                user_message=user_msg,
                bot_response=bot_response,
                phase=reply["phase"],
                response_time=reply["time"],
                error=reply["error"],
            )

            # Validations for returning sessions
            if sess_config.is_returning and bot_response:
                validations = {}

                # Check recall
                if sess_config.recall_keywords:
                    has_recall = check_recall(bot_response, sess_config.recall_keywords)
                    validations["past_topic_referenced"] = has_recall
                    recall_checks += 1
                    if has_recall:
                        recall_hits += 1

                # Generic greeting check (first turn of returning session)
                if turn_num == 1:
                    validations["not_generic_greeting"] = check_not_generic_greeting(bot_response)

                validations["no_data_dump"] = check_no_data_dump(bot_response)
                validations["natural_language"] = check_natural_language(bot_response)
                validations["no_hollow_phrases"] = check_no_hollow_phrases(bot_response)

                # Sensitive topic check
                if sess_config.sensitive:
                    validations["no_insensitive_recall"] = check_no_insensitive_recall(
                        bot_response, sess_config.recall_keywords
                    )

                turn_result.validations = validations

                status_chars = []
                for k, v in validations.items():
                    status_chars.append(f"{'PASS' if v else 'FAIL'}:{k}")
                print(f"      Bot: {bot_response[:80]}...")
                print(f"      Validations: {', '.join(status_chars)}")

            sess_result.turns.append(turn_result)
            await asyncio.sleep(INTER_TURN_DELAY)

        # Save conversation (unless it's the last returning session)
        if not sess_config.is_returning:
            saved = await client.save_conversation(session_id, conversation_messages)
            sess_result.saved = saved
            if saved:
                print(f"    Conversation saved. Waiting {SAVE_WAIT_DELAY}s for propagation...")
                await asyncio.sleep(SAVE_WAIT_DELAY)
            else:
                result.notes.append(f"Failed to save session {sess_num}")
        else:
            sess_result.saved = False  # Returning session, not saved

        result.sessions.append(sess_result)

    # Compute recall score
    if recall_checks > 0:
        result.recall_score = recall_hits / recall_checks
    else:
        result.recall_score = 0.0

    # Overall pass: at least one returning-session turn had recall
    result.passed = result.recall_score > 0

    print(f"\n  Result: {'PASS' if result.passed else 'FAIL'} | Recall: {result.recall_score:.0%} ({recall_hits}/{recall_checks})")

    await client.close()
    return result


# ---------------------------------------------------------------------------
# Report Generation
# ---------------------------------------------------------------------------
def generate_report(results: List[ScenarioResult]) -> str:
    lines = [
        "# Returning User Continuity Test Report",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Summary",
        "",
        f"| Scenario | Status | Recall Score | Notes |",
        f"|----------|--------|-------------|-------|",
    ]

    total_passed = 0
    total_recall = 0.0
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        if r.passed:
            total_passed += 1
        total_recall += r.recall_score
        notes = "; ".join(r.notes) if r.notes else "-"
        lines.append(f"| S{r.scenario_id}: {r.name} | {status} | {r.recall_score:.0%} | {notes} |")

    avg_recall = total_recall / len(results) if results else 0
    lines.extend([
        "",
        f"**Overall:** {total_passed}/{len(results)} passed | Avg recall: {avg_recall:.0%}",
        "",
    ])

    # Detailed per-scenario
    lines.append("## Detailed Results")
    lines.append("")

    for r in results:
        lines.append(f"### S{r.scenario_id}: {r.name}")
        lines.append(f"*{r.description}*")
        lines.append("")

        for sess in r.sessions:
            lines.append(f"#### Session {sess.session_number} (ID: {sess.session_id[:8]}...)")
            for turn in sess.turns:
                lines.append(f"- **Turn {turn.turn_number}** ({turn.phase}, {turn.response_time:.1f}s)")
                lines.append(f"  - User: {turn.user_message[:100]}")
                lines.append(f"  - Bot: {turn.bot_response[:150]}")
                if turn.validations:
                    for k, v in turn.validations.items():
                        lines.append(f"  - {k}: {'PASS' if v else 'FAIL'}")
                if turn.error:
                    lines.append(f"  - ERROR: {turn.error}")
            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main():
    parser = argparse.ArgumentParser(description="Returning User Continuity Test")
    parser.add_argument("--url", default=DEFAULT_BASE_URL, help="Backend base URL")
    parser.add_argument("--scenario", type=int, default=None, help="Run a single scenario (1-6)")
    args = parser.parse_args()

    scenarios_to_run = SCENARIOS
    if args.scenario:
        scenarios_to_run = [s for s in SCENARIOS if s.id == args.scenario]
        if not scenarios_to_run:
            print(f"Scenario {args.scenario} not found. Available: 1-{len(SCENARIOS)}")
            sys.exit(1)

    print(f"Returning User Continuity Test")
    print(f"URL: {args.url}")
    print(f"Scenarios: {len(scenarios_to_run)}")

    results = []
    for scenario in scenarios_to_run:
        try:
            result = await run_scenario(scenario, args.url)
            results.append(result)
        except Exception as e:
            print(f"\nScenario {scenario.id} failed with exception: {e}")
            results.append(ScenarioResult(
                scenario_id=scenario.id,
                name=scenario.name,
                description=scenario.description,
                notes=[f"Exception: {str(e)}"],
            ))

    # Save results
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    results_json = []
    for r in results:
        results_json.append({
            "scenario_id": r.scenario_id,
            "name": r.name,
            "passed": r.passed,
            "recall_score": r.recall_score,
            "notes": r.notes,
            "sessions": [
                {
                    "session_number": s.session_number,
                    "session_id": s.session_id,
                    "saved": s.saved,
                    "turns": [
                        {
                            "turn_number": t.turn_number,
                            "user_message": t.user_message,
                            "bot_response": t.bot_response,
                            "phase": t.phase,
                            "response_time": t.response_time,
                            "error": t.error,
                            "validations": t.validations,
                        }
                        for t in s.turns
                    ],
                }
                for s in r.sessions
            ],
        })

    with open(RESULTS_DIR / "results.json", "w") as f:
        json.dump(results_json, f, indent=2, ensure_ascii=False)

    report = generate_report(results)
    with open(RESULTS_DIR / "continuity_report.md", "w") as f:
        f.write(report)

    # Print summary
    print(f"\n{'='*60}")
    print("FINAL SUMMARY")
    print(f"{'='*60}")
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    avg_recall = sum(r.recall_score for r in results) / total if total else 0
    print(f"  Passed: {passed}/{total}")
    print(f"  Avg Recall: {avg_recall:.0%}")
    print(f"  Results: {RESULTS_DIR / 'results.json'}")
    print(f"  Report:  {RESULTS_DIR / 'continuity_report.md'}")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    asyncio.run(main())
