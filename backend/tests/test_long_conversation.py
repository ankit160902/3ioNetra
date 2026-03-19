"""
Long Conversation Stress Test for 3ioNetra Mitra
=================================================
Tests the system's ability to handle long multi-turn conversations
(50–200 turns) without errors. Runs 6 scenarios totalling ~550 turns
against the live API, validates every turn, computes aggregate metrics,
and generates a detailed report with improvement plan if needed.

Known issues being watched:
  - conversation_history grows unboundedly (no truncation)
  - memory.user_quotes, memory.emotional_arc grow unboundedly
  - LLM prompt uses only last 8 messages — context loss expected
  - last_guidance_turn is never set after guidance → oscillation control broken
  - MAX_CLARIFICATION_TURNS=4 → forces guidance by turn 4
  - Session TTL = 60 min (sufficient for ~200 turns at 3s/turn ≈ 10 min)

Usage:
    python tests/test_long_conversation.py
    python tests/test_long_conversation.py --scenario 1
    python tests/test_long_conversation.py --url http://localhost:8080
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
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DEFAULT_BASE_URL = "http://localhost:8080"
TEST_EMAIL = "test_stress_eval@test.com"
TEST_PASSWORD = "TestStress2026!"
TEST_NAME = "Stress Test Evaluator"
RESULTS_DIR = Path(__file__).parent / "long_conversation_results"
REQUEST_TIMEOUT = 90.0
INTER_TURN_DELAY = 2.0  # seconds between turns

VALID_PHASES = ["listening", "clarification", "guidance", "synthesis", "closure"]

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
# Personas
# ---------------------------------------------------------------------------
PERSONAS = {
    "meera": {
        "name": "Meera",
        "age_group": "50-60",
        "gender": "female",
        "profession": "Teacher",
        "preferred_deity": "Krishna",
        "location": "Delhi, India",
        "spiritual_interests": ["bhakti", "kirtan", "temples"],
    },
    "arjun": {
        "name": "Arjun",
        "age_group": "30-40",
        "gender": "male",
        "profession": "Software Engineer",
        "preferred_deity": "Shiva",
        "location": "Bangalore, India",
        "spiritual_interests": ["meditation", "yoga", "vedanta"],
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
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class ScenarioPhase:
    name: str
    turn_start: int  # inclusive, 1-based
    turn_end: int     # inclusive, 1-based
    message_pool: list[str]


@dataclass
class StressScenario:
    id: int
    title: str
    persona: dict
    total_turns: int
    phases: list[ScenarioPhase]
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
    response_time: float = 0.0  # seconds
    word_count: int = 0
    error: str = ""


@dataclass
class ScenarioResult:
    scenario_id: int
    title: str
    persona_name: str
    total_turns: int
    turn_results: list[TurnResult]
    passed: int = 0
    failed: int = 0
    errors: int = 0
    error: str = ""


# ---------------------------------------------------------------------------
# Message pools per scenario
# ---------------------------------------------------------------------------

# S1: Grief Journey — 100 turns
GRIEF_OPENING = [
    "namaste",
    "aaj mann bahut bhari hai",
    "meri maa nahi rahi... ek mahina ho gaya",
    "ek mahina ho gaya unhe gaye hue",
    "aaj subah unki photo dekhi aur rona aa gaya",
]
GRIEF_DEEPENING = [
    "unke bina sab kuch soona lagta hai",
    "raat ko yaad aati hai unki",
    "ghar mein unki jagah khaali khaali lagti hai",
    "unka kamra waise hi rakha hai, kuch hatane ka mann nahi karta",
    "subah chai banate waqt unki yaad aati hai, woh hamesha pehle uthti thi",
    "unki sari abhi bhi almari mein hai, khushbu aati hai unki",
    "kabhi kabhi lagta hai woh abhi aayengi aur bolein gi kuch",
    "festival pe unke bina kaise manaun?",
    "unke haath ka khana bahut yaad aata hai",
    "kabhi kabhi unse baat karti hoon akele mein",
    "papa bahut toot gaye hain unke bina",
    "bhai kehta hai strong raho par main kaise strong rahun",
    "sapne mein aati hain kabhi kabhi, phir uthke rona aata hai",
    "unke jaane ke baad ghar mein koi hansi nahi rahi",
    "logon ki condolences ab band ho gayi, par dard toh wahi hai",
]
GRIEF_ANGER = [
    "bhagwan ne unhe kyu le liya? woh toh bahut acchi thi",
    "kyu mere saath hi aisa hota hai",
    "doctor ne agar pehle diagnose kar liya hota toh shayad...",
    "bahut gussa aata hai bhagwan pe",
    "maine unki kitni seva ki, phir bhi bhagwan ne yeh kiya",
    "family mein koi samajhta nahi mera dard",
    "sab kehte hain time heals, par kab?",
    "bhai se ladai ho gayi property ke mamle pe, maa ke jaane ke baad sab badal gaye",
    "aaj hospital ke saamne se guzri, bahut gussa aaya",
    "kya maa ne koi paap kiya tha jo itni takleef mili unhe?",
    "beti kehti hai nani ko bhool jao, par bhoolun kaise",
    "ghar mein har cheez unki yaad dilati hai, gussa aata hai khud pe",
    "kya karu main inn sab se door chali jaun kahin",
    "relatives sirf property ke liye aaye the, maa ki unhe koi parwaah nahi thi",
    "bahut akeli ho gayi hoon maa ke bina",
]
GRIEF_ACCEPTANCE = [
    "aaj pehli baar bina roye unki photo dekhi",
    "dhire dhire samajh aa raha hai ki woh nahi aayengi wapas",
    "papa ko sambhalna padega, unke liye strong rehna hoga",
    "maa hamesha kehti thi ki zyada rona accha nahi",
    "unki baatein yaad karke kabhi kabhi hasi bhi aa jaati hai",
    "kal unka favorite khana banaya, accha laga",
    "ek din accha guzra bina zyada rone ke",
    "shayad maa yahi chahti thi ki main khush rahun",
    "unke liye kuch accha karna chahti hoon, koi daan ya seva",
    "aaj mandir gayi, thoda sa chain mila",
    "pooja mein mann lagane ki koshish ki aaj",
    "aaj garden mein baithi, maa ko phool bahut pasand the",
    "beti se maa ke baare mein baat ki aaj, accha laga",
    "maa ki ek diary mili, usme bahut kuch likha hai",
    "dhire dhire jee rahi hoon, par unki yaad hamesha rahegi",
]
GRIEF_OPENING_TO_SPIRITUAL = [
    "kya maa ki aatma shaanti mein hogi?",
    "kya garuda puran mein mrityu ke baare mein kuch kaha gaya hai?",
    "maa ke liye kaunsa mantra japun?",
    "kya shraddh karna zaruri hai? papa kehte hain karna chahiye",
    "kya aatma phir se janam leti hai?",
    "maa ne marte waqt Om bola tha, kya iska koi matlab hai?",
    "kya unke liye gita ka paath karwana chahiye?",
    "mandir mein jaake maa ke liye prarthna karti hoon, sahi hai na?",
    "ek pandit ne kaha maa ki aatma bhatak rahi hai, bahut dar lag gaya",
    "kya 13ven din ke baad aatma shant ho jaati hai?",
    "maa ko shanti mile, iske liye kya karun?",
    "bhagwat gita mein mrityu ke baare mein kya kaha gaya hai?",
    "kya mujhe pooja path zyada karni chahiye maa ke liye?",
    "mujhe koi mantra bataiye jo maa ki aatma ki shanti ke liye ho",
    "maa ke favourite bhajan sunti hoon, lagta hai woh sun rahi hain",
]
GRIEF_CLOSURE = [
    "bahut accha laga aapse baat karke",
    "thoda halka mehsoos ho raha hai",
    "kal phir baat karungi",
    "shukriya aapka, maa hoti toh woh bhi aisa hi kehti",
    "aapki baatein mann ko chhu gayi",
]

# S2: Career Crisis Spiral — 75 turns
CAREER_OPENING = [
    "hey",
    "aaj bahut bura din hai",
    "company ne layoff kar diya mujhe",
    "5 saal kaam kiya aur aise nikaal diya",
    "email se notice mila, ek meeting bhi nahi ki",
]
CAREER_JOB_SEARCH = [
    "resume update kar raha hoon par confidence nahi hai",
    "3 interviews diye, sab mein reject ho gaya",
    "linkedin pe apply karte karte thak gaya",
    "ek company ne ghosting kar di, 3 round clear kiye the",
    "market bahut kharab hai, koi job nahi mil rahi",
    "freshers ko zyada prefer kar rahe hain, experienced se dar lagte hain",
    "savings 3 mahine ki hai bas, uske baad kya karunga",
    "ek interview mein bola they need someone younger, indirect bol diya",
    "networking karna padta hai par mera mann nahi lagta",
    "kabhi kabhi lagta hai galat field choose ki",
    "resume pe gap aa raha hai, aur mushkil ho rahi hai",
    "freelance try kiya par stable nahi hai",
    "ek offer aaya par salary half thi, le lun kya?",
    "recruiter ne bola overqualified ho, kya matlab hai iska",
    "har rejection ke baad aur toota hua mehsoos hota hoon",
    "portfolio update kar raha hoon par lagta hai sab bekar hai",
    "startup join karne ka socha par risky hai",
    "coding test diya, time khatam ho gaya, bahut bura laga",
    "aaj phir rejection email aayi",
    "upskilling kar raha hoon par naye tools seekhne mein time lagta hai",
]
CAREER_SELF_DOUBT = [
    "lagta hai main kisi kaam ka nahi hoon",
    "mere batch ke sab log VP ban gaye, main yahan berozgar",
    "kya sach mein meri skills outdated ho gayi hain?",
    "wife ki aankhon mein disappointment dikhti hai",
    "ghar mein baith ke bore ho raha hoon, khud se nafrat hoti hai",
    "subah uthne ka mann nahi karta, kya karun fir bhi?",
    "interview mein haath kaanpte hain ab",
    "lagta hai luck mera saath nahi deta",
    "bachpan mein sapne the, ab sab toot gaye",
    "mujhe apni value samajh nahi aa rahi",
    "mere colleagues ne toh job dhundh li, main hi peeche reh gaya",
    "kya main over-thinker hoon ya sach mein problem hai?",
    "aaj mirror mein dekha, thaka hua aadmi dikha",
    "lagta hai main fail ho gaya life mein",
    "confidence bilkul khatam ho gaya hai",
    "ek time tha jab log mujhse advice lete the, ab main...",
    "kya spirituality se kuch fayda ho sakta hai career mein?",
    "mann karta hai sab chhod ke kahin chala jaun",
    "bahut insecure feel hota hai",
    "comparison se bachna mushkil hai social media pe",
]
CAREER_FAMILY_PRESSURE = [
    "papa har roz poochte hain job mili kya, kya bataun",
    "wife ke parents taunt maarte hain",
    "bacchon ki fees ka time aa raha hai, paisa nahi hai",
    "EMI bounce ho gayi ek, bahut sharam aayi",
    "biwi se ladai ho gayi paise ke mamle pe",
    "maa ro rahi thi phone pe, kuch bol nahi paaya",
    "rishtedaar poochte hain kya kar rahe ho, jhooth bolna padta hai",
    "ek dost ne paise maange the wapas, de nahi paaya",
    "ghar ka mahaul bahut tense hai",
    "wife ne bola apne papa se maang lo, par self-respect...",
    "bacche school mein poochte hain papa kya karte hain",
    "insurance ki EMI bhi nahi bhar paaya is mahine",
    "bhai ne help offer ki par leni nahi chahta",
    "kya part time kuch karu? uber ya delivery?",
    "family function mein jaane se darta hoon, log poochenge",
    "biwi ka support hai par kitne din chahiye patience",
    "maa ne bola bhagwan pe bharosa rakho, par kab tak",
    "financial advisor se mila, usne bhi dar diya",
    "credit card se grocery le raha hoon, yeh kab tak",
    "bacchon ke saamne strong dikhana padta hai",
]
CAREER_REBUILDING = [
    "ek chhoti company se call aaya, interview schedule hua",
    "kal interview gaya, accha gaya lag raha hai",
    "ek freelance project mila, thoda confidence aaya",
    "wife ne bola proud hai mujhpe ki try kar raha hoon",
    "naya skill seekha aaj, thoda accha laga",
    "ek purane colleague ne referral diya, hopefully kaam aaye",
    "aaj gym gaya bahut dino baad, energy aayi",
    "papa se baat ki honestly, unhone samjha",
    "interview clear ho gaya ek round, fingers crossed",
    "chota sa kaam mila, par start toh hai",
]

# S3: Rapid Topic Switching — 50 turns
TOPIC_EXAMS = [
    "exam aa rahe hain, bahut tension hai",
    "padhai mein mann nahi lag raha",
    "syllabus bahut zyada hai aur time kam",
    "kal test tha, bilkul nahi hua",
    "topper se compare karta hoon khud ko",
    "raat ko neend nahi aati exam ke tension se",
    "mock test mein marks kam aaye",
    "kya padhai mein concentration badhane ka koi tarika hai?",
]
TOPIC_RELATIONSHIP = [
    "girlfriend se jhagda ho gaya",
    "woh mujhse baat nahi kar rahi",
    "uske friends kehte hain main accha nahi hoon uske liye",
    "kya mujhe sorry bol dena chahiye even if i was right?",
    "relationship mein trust issues hain",
    "uske ex ka message aaya, jealousy ho rahi hai",
    "kya pyaar mein itna struggle normal hai?",
    "woh kehti hai i dont give her enough time",
]
TOPIC_FAMILY = [
    "mummy papa mein aajkal ladai hoti hai",
    "ghar ka mahaul bahut negative hai",
    "papa ki daant sunne ki aadat ho gayi hai",
    "chhote bhai ko sab kuch milta hai, mujhe nahi",
    "mummy ko BP hai, tension hoti hai",
    "ghar mein paise ki tangi hai",
    "dadi ka health kharab hai",
    "joint family mein privacy nahi milti",
]
TOPIC_EXISTENTIAL = [
    "kabhi lagta hai sab bekar hai",
    "life ka point kya hai?",
    "sab same cycle mein hai — padho, kaam karo, mar jao",
    "kya bhagwan sach mein hai?",
    "agar karma real hai toh bure logon ko accha kyu milta hai?",
    "death ke baad kya hota hai?",
    "kabhi kabhi bahut akela mehsoos hota hoon",
    "kya meditation se kuch fayda hoga?",
]
TOPIC_SPIRITUAL = [
    "bhagwat gita padhna shuru kiya, samajh nahi aa raha",
    "meditation try ki par mann nahi laga",
    "mandir jaana chahta hoon par dost mazaak udayenge",
    "kya hanuman chalisa se sach mein fayda hota hai?",
    "yoga karna shuru kiya, thoda accha feel hua",
    "kya koi accha mantra bata sakte ho?",
    "spirituality mein interest aa raha hai par kahan se shuru karun",
    "kya daily pooja zaruri hai?",
    "ek aur baat, meditation kaise karun properly?",
    "hanuman ji ki katha sunna accha lagta hai",
]

# S4: Marathon Emotional Venting — 200 turns
VENT_WORK_BURNOUT = [
    "office mein aaj phir 12 ghante kaam kiya",
    "boss ne last minute pe deadline change kar di",
    "weekend pe bhi kaam karna pad raha hai",
    "meeting ke baad meeting, kaam kab karun?",
    "colleague ne mera credit le liya project ka",
    "appraisal mein low rating di, bahut unfair hai",
    "HR se complaint ki par kuch nahi hua",
    "burnout feel ho raha hai, energy nahi hai",
    "subah office jaane ka mann nahi karta",
    "coding se mann uth gaya hai, pehle passion tha",
    "manager toxic hai, micro-manage karta hai",
    "ek aur sprint, ek aur deadline, kabhi khatam nahi hota",
    "lunch skip karna padta hai meetings ki wajah se",
    "ghar jaake bhi laptop kholna padta hai",
    "weekend pe sirf sona chahta hoon, kuch karne ka mann nahi",
    "anxiety attacks aa rahe hain office mein",
    "resign karna chahta hoon par EMI hai",
    "chai peete peete bhi slack notifications aati hain",
    "vacation liya par boss ne call kiya, chutti bhi nahi milti",
    "team mein sab darte hain boss se, koi kuch nahi bolta",
    "aaj toh bahut zyada ho gaya, almost ro diya cabin mein",
    "kya yahi zindagi hai? subah se raat tak kaam?",
    "dost milte nahi kyunki time hi nahi milta",
    "health bhi kharab ho rahi hai baithe baithe",
    "back pain ho gaya hai, doctor ne bola stress hai",
]
VENT_RELATIONSHIP = [
    "biwi kehti hai tum ghar pe bhi nahi ho mentally",
    "bacchon ke saath time nahi bita paata",
    "kal anniversary thi, bhool gaya tha",
    "biwi ne rote hue bola i feel like a single parent",
    "ghar aake sirf phone dekhta hoon, baat nahi karta",
    "biwi ke parents kehte hain unhe acche se rakho",
    "relationship mein romance khatam ho gaya",
    "kabhi date pe jaate the, ab yaad bhi nahi kab gaye the",
    "biwi ne bola agar change nahi aaya toh woh chali jayegi",
    "baccha bola papa aap kabhi mere saath nahi khelyte",
    "family vacation plan kiya par cancel karna pada kaam ki wajah se",
    "wife se ladai ho gayi chhoti si baat pe",
    "lagta hai accha husband nahi hoon main",
    "shaadi ke pehle bahut plans the, ab sirf EMI hai",
    "biwi ka bhi career suffer ho raha hai meri wajah se",
    "kabhi kabhi lagta hai alone better hota",
    "ghar aata hoon toh sab ki demands shuru ho jaati hain",
    "kya relationship mein efforts one-sided hote hain?",
    "wife se sorry bola, par baar baar sorry bolna kab tak?",
    "biwi ne counseling suggest ki, par time kahan hai?",
    "ek raat acchi baat hui, phir subah se phir wahi sab",
    "bacchon ko school chhod ke aaya aaj, accha laga",
    "wife ne khana banaya special aaj, guilty feel hua",
    "kya main selfish hoon jo sirf kaam karta hoon?",
    "relationship repair karna hai par energy nahi hai",
]
VENT_HEALTH_ANXIETY = [
    "kal raat seene mein dard hua, bahut dar gaya",
    "google pe symptoms search ki, aur dar gaya",
    "doctor ke paas jaane se darta hoon, kya pata kya nikle",
    "weight badh gaya hai, exercise ka time nahi",
    "neend nahi aati raat ko, din mein drowsy rehta hoon",
    "anxiety ki wajah se haath kaanpte hain",
    "doctor ne bola stress reduce karo, par kaise?",
    "blood test mein cholesterol high aaya",
    "papa ko heart attack tha, mujhe bhi toh nahi hoga?",
    "har chhoti si body sensation pe panic hota hai",
    "meditation try ki health ke liye par mann nahi laga",
    "yoga join karna hai par subah uthna mushkil hai",
    "khana bhi theek se nahi kha paata, acidity hoti hai",
    "ek dost ko cancer hua, ab har cheez se darta hoon",
    "health insurance renew karwana hai, costly hai bahut",
    "tablet zyada le raha hoon painkiller ki, pata hai galat hai",
    "gym join kiya par 3 din mein chhod diya",
    "raat ko palpitations aati hain, neend toot jaati hai",
    "kya ayurveda se kuch fayda hoga?",
    "body weak feel hoti hai, vitamin deficiency hogi shayad",
    "aaj bahut thaka hua feel ho raha hai bina kuch kiye",
    "doctor ne bola lifestyle change karo, easy to say",
    "kabhi kabhi chest tight lagta hai, anxiety hai ya sach mein?",
    "health ki chinta se aur stress ho raha hai",
    "yoga class ka schedule dekhna hai, kab jaun?",
]
VENT_EXISTENTIAL_MIX = [
    "sab kuch saath mein ho raha hai, sambhalna mushkil hai",
    "kaam bhi kharab, health bhi kharab, relationship bhi",
    "lagta hai main zindagi mein kuch theek nahi kar paaya",
    "kya point hai itna struggle karne ka?",
    "bacchon ke liye jee raha hoon, warna...",
    "dost se mila, usne bola tu bahut change ho gaya hai",
    "pehle hasne waala tha, ab chup rehta hoon",
    "aaj ek purani photo dekhi, kitna khush tha tab",
    "kya spirituality se kuch help mil sakti hai?",
    "mann karta hai sab chhod ke himalaya chala jaun",
    "lagta hai rat race mein phas gaya hoon",
    "kya yahi destiny thi meri?",
    "kabhi lagta hai kuch change hoga, kabhi lagta hai nahi",
    "ek din accha guzra, socha share karun",
    "aaj thoda better feel ho raha hai, pata nahi kyu",
    "kya dhyan se mann ko shanti mil sakti hai?",
    "zindagi ek circle hai, wahi problems baar baar",
    "kya bhagwan test kar rahe hain mujhe?",
    "thoda sa hope feel ho raha hai aaj",
    "shukriya sun ne ke liye, bahut accha lagta hai",
    "ek chhoti si acchi baat hui aaj office mein",
    "biwi ne hug kiya aaj, bahut accha laga",
    "shayad sab theek ho jayega dhire dhire",
    "aaj mandir gaya bahut dino baad",
    "aaj meditation ki 5 minute, accha laga",
]

# S5: Oscillation Stress Test — 75 turns
OSCILLATION_VENT = [
    "bahut pareshan hoon yaar",
    "sab kuch ulta pulta ho raha hai life mein",
    "koi samajhta nahi mujhe",
    "ghar mein problems hain, office mein problems hain",
    "bahut frustrating hai yeh sab",
    "thak gaya hoon inn sab se",
    "har din wahi problems, koi solution nahi",
    "mann bahut heavy hai aaj",
    "aaj phir se bahut bura din tha",
    "lagta hai kuch theek nahi hoga",
    "dost bhi busy hain, kisi se baat nahi kar paata",
    "akela mehsoos hota hoon",
]
OSCILLATION_ASK_GUIDANCE = [
    "koi guidance do na, kya karun?",
    "kuch batao na spiritually kya kar sakta hoon?",
    "koi mantra hai jo peace de sake?",
    "bhagwat gita mein is situation ke baare mein kya kaha hai?",
    "meditation kaise karun? batao na step by step",
    "mujhe koi raasta dikhao",
    "kya dhyan lagane se mann shant hoga?",
    "hanuman chalisa padhu kya? fayda hoga?",
    "koi prayer bataiye",
    "spiritually grow kaise karun?",
]
OSCILLATION_REJECT = [
    "hmm theek hai, par practical mein kaise karun?",
    "yeh sab theek hai par mera problem solve nahi hoga isse",
    "mantra se kya hoga, problem toh real world mein hai",
    "meditation try kiya tha, kuch nahi hua",
    "yeh sab pehle bhi try kiya hai",
]

# S6: Monosyllabic Marathon — 50 turns
MONO_GREET = ["hey", "hi", "hii"]
MONO_SHORT = [
    "hmm",
    "yeah",
    "ok",
    "idk",
    "maybe",
    "sure",
    "whatever",
    "fine",
    "nah",
    "meh",
    "kinda",
    "not really",
    "i guess",
    "dont know",
    "nothing",
    "same as before",
    "just like that",
    "its ok",
    "cant explain",
    "complicated",
    "theek hai",
    "pata nahi",
    "kuch nahi",
    "bas",
    "haan",
    "nahi",
    "accha",
    "sab same hai",
    "kuch naya nahi",
    "wahi sab",
    "thoda better",
    "thoda",
    "aaj bhi",
    "wahi",
    "pehle jaisa",
    "no change",
    "still bad",
    "still ok",
    "dunno",
    "it is what it is",
    "ugh",
    "sigh",
    "tired",
    "exhausted",
    "lonely",
    "bored",
    "sad",
]


# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------
def build_scenarios() -> list[StressScenario]:
    return [
        StressScenario(
            id=1,
            title="Grief Journey",
            persona=PERSONAS["meera"],
            total_turns=100,
            description="Long grief processing: opening → deepening → anger → acceptance → spiritual → closure",
            phases=[
                ScenarioPhase("opening", 1, 5, GRIEF_OPENING),
                ScenarioPhase("deepening", 6, 20, GRIEF_DEEPENING),
                ScenarioPhase("anger", 21, 40, GRIEF_ANGER),
                ScenarioPhase("acceptance", 41, 60, GRIEF_ACCEPTANCE),
                ScenarioPhase("spiritual_opening", 61, 80, GRIEF_OPENING_TO_SPIRITUAL),
                ScenarioPhase("closure_attempts", 81, 100, GRIEF_CLOSURE + GRIEF_ACCEPTANCE + GRIEF_OPENING_TO_SPIRITUAL),
            ],
        ),
        StressScenario(
            id=2,
            title="Career Crisis Spiral",
            persona=PERSONAS["arjun"],
            total_turns=75,
            description="Layoff → job search → self-doubt → family pressure → rebuilding",
            phases=[
                ScenarioPhase("opening", 1, 5, CAREER_OPENING),
                ScenarioPhase("job_search", 6, 25, CAREER_JOB_SEARCH),
                ScenarioPhase("self_doubt", 26, 45, CAREER_SELF_DOUBT),
                ScenarioPhase("family_pressure", 46, 65, CAREER_FAMILY_PRESSURE),
                ScenarioPhase("rebuilding", 66, 75, CAREER_REBUILDING),
            ],
        ),
        StressScenario(
            id=3,
            title="Rapid Topic Switching",
            persona=PERSONAS["rohan"],
            total_turns=50,
            description="Jumps topics every 5-8 turns: exams → relationship → family → existential → exams → spiritual",
            phases=[
                ScenarioPhase("exams_1", 1, 8, TOPIC_EXAMS),
                ScenarioPhase("relationship", 9, 16, TOPIC_RELATIONSHIP),
                ScenarioPhase("family", 17, 24, TOPIC_FAMILY),
                ScenarioPhase("existential", 25, 32, TOPIC_EXISTENTIAL),
                ScenarioPhase("exams_2", 33, 40, TOPIC_EXAMS),
                ScenarioPhase("spiritual", 41, 50, TOPIC_SPIRITUAL),
            ],
        ),
        StressScenario(
            id=4,
            title="Marathon Emotional Venting",
            persona=PERSONAS["priya"],
            total_turns=200,
            description="Longest test: work burnout → relationship → health anxiety → existential mix (200 turns)",
            phases=[
                ScenarioPhase("work_burnout", 1, 50, VENT_WORK_BURNOUT),
                ScenarioPhase("relationship", 51, 100, VENT_RELATIONSHIP),
                ScenarioPhase("health_anxiety", 101, 150, VENT_HEALTH_ANXIETY),
                ScenarioPhase("existential_mix", 151, 200, VENT_EXISTENTIAL_MIX),
            ],
        ),
        StressScenario(
            id=5,
            title="Oscillation Stress Test",
            persona=PERSONAS["vikram"],
            total_turns=75,
            description="Every 8-12 turns: asks for guidance, then reverts to venting. Tests oscillation control.",
            phases=[
                # Alternating vent/ask cycles
                ScenarioPhase("vent_1", 1, 8, OSCILLATION_VENT),
                ScenarioPhase("ask_1", 9, 10, OSCILLATION_ASK_GUIDANCE),
                ScenarioPhase("reject_1", 11, 12, OSCILLATION_REJECT),
                ScenarioPhase("vent_2", 13, 22, OSCILLATION_VENT),
                ScenarioPhase("ask_2", 23, 24, OSCILLATION_ASK_GUIDANCE),
                ScenarioPhase("reject_2", 25, 26, OSCILLATION_REJECT),
                ScenarioPhase("vent_3", 27, 36, OSCILLATION_VENT),
                ScenarioPhase("ask_3", 37, 38, OSCILLATION_ASK_GUIDANCE),
                ScenarioPhase("reject_3", 39, 40, OSCILLATION_REJECT),
                ScenarioPhase("vent_4", 41, 50, OSCILLATION_VENT),
                ScenarioPhase("ask_4", 51, 52, OSCILLATION_ASK_GUIDANCE),
                ScenarioPhase("reject_4", 53, 54, OSCILLATION_REJECT),
                ScenarioPhase("vent_5", 55, 64, OSCILLATION_VENT),
                ScenarioPhase("ask_5", 65, 66, OSCILLATION_ASK_GUIDANCE),
                ScenarioPhase("vent_6", 67, 75, OSCILLATION_VENT),
            ],
        ),
        StressScenario(
            id=6,
            title="Monosyllabic Marathon",
            persona=PERSONAS["ananya"],
            total_turns=50,
            description="Short responses (hmm, yeah, ok, idk) for 50 turns. Tests bot patience.",
            phases=[
                ScenarioPhase("greeting", 1, 1, MONO_GREET),
                ScenarioPhase("monosyllabic", 2, 50, MONO_SHORT),
            ],
        ),
    ]


ALL_SCENARIOS = build_scenarios()


def get_message_for_turn(scenario: StressScenario, turn_num: int) -> str:
    """Get the message for a given turn by finding the matching phase and cycling its pool."""
    for phase in scenario.phases:
        if phase.turn_start <= turn_num <= phase.turn_end:
            idx = (turn_num - phase.turn_start) % len(phase.message_pool)
            return phase.message_pool[idx]
    # Fallback — should not happen
    return "haan, bolo"


# ---------------------------------------------------------------------------
# Validation engine
# ---------------------------------------------------------------------------
def run_per_turn_validations(
    response: str,
    api_data: dict,
    turn_num: int,
    response_time: float,
    prev_response: str,
) -> list[dict]:
    """Run all per-turn validations. Returns list of {description, passed, detail}."""
    results = []

    # 1. response_not_empty
    passed = len(response.strip()) > 0
    results.append({
        "description": "Response is non-empty",
        "passed": passed,
        "detail": f"{len(response)} chars",
    })

    # 2. max_words <= 150
    word_count = len(response.split())
    results.append({
        "description": "Response under 150 words",
        "passed": word_count <= 150,
        "detail": f"{word_count} words (limit 150)",
    })

    # 3. min_words >= 3
    results.append({
        "description": "Response at least 3 words",
        "passed": word_count >= 3,
        "detail": f"{word_count} words (min 3)",
    })

    # 4. no_markdown
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
    results.append({
        "description": "No markdown formatting",
        "passed": len(violations) == 0,
        "detail": f"violations: {violations[:3]}" if violations else "clean",
    })

    # 5. no_hollow_phrases
    found_hollow = [h for h in HOLLOW_PHRASES if h in response.lower()]
    results.append({
        "description": "No hollow/banned phrases",
        "passed": len(found_hollow) == 0,
        "detail": f"found: {found_hollow}" if found_hollow else "clean",
    })

    # 6. no_product_urls
    url_patterns = ["my3ionetra.com", "3ionetra.com/product", "http", "www."]
    found_urls = [p for p in url_patterns if p in response.lower()]
    results.append({
        "description": "No product URLs in text",
        "passed": len(found_urls) == 0,
        "detail": f"found URLs: {found_urls}" if found_urls else "clean",
    })

    # 7. no_repetition (not identical to previous bot response)
    if prev_response:
        similarity = SequenceMatcher(None, response.lower(), prev_response.lower()).ratio()
        is_repeated = similarity > 0.80
        results.append({
            "description": "No repetition (>80% similar to prev)",
            "passed": not is_repeated,
            "detail": f"similarity: {similarity:.2f}" + (" REPEATED" if is_repeated else ""),
        })
    else:
        results.append({
            "description": "No repetition (>80% similar to prev)",
            "passed": True,
            "detail": "first response, skipped",
        })

    # 8. response_time <= 30s (warn at 15s)
    passed_rt = response_time <= 30.0
    warning = " (WARNING: slow)" if 15.0 < response_time <= 30.0 else ""
    results.append({
        "description": "Response time under 30s",
        "passed": passed_rt,
        "detail": f"{response_time:.1f}s{warning}",
    })

    # 9. http_200 — if we got here, it's 200. Errors are handled before calling this.
    results.append({
        "description": "HTTP 200 OK",
        "passed": True,
        "detail": "ok",
    })

    # 10. valid_phase
    phase = api_data.get("phase", "")
    results.append({
        "description": "Valid conversation phase",
        "passed": phase in VALID_PHASES,
        "detail": f"phase='{phase}'" + ("" if phase in VALID_PHASES else f" (expected one of {VALID_PHASES})"),
    })

    return results


def run_milestone_validations(
    scenario_result: ScenarioResult,
    turn_num: int,
) -> list[dict]:
    """Run milestone validations at specific checkpoints."""
    results = []
    trs = scenario_result.turn_results

    if turn_num == 10:
        # Session still alive, signals being collected
        last_tr = trs[-1] if trs else None
        if last_tr:
            has_signals = bool(last_tr.signals)
            results.append({
                "description": "[Milestone T10] Session alive, signals collected",
                "passed": not last_tr.error and has_signals,
                "detail": f"signals: {list(last_tr.signals.keys())}" if has_signals else "no signals yet",
            })

    elif turn_num == 25:
        # At least 1 guidance phase has occurred
        has_guidance = any(tr.phase == "guidance" for tr in trs)
        results.append({
            "description": "[Milestone T25] At least 1 guidance phase occurred",
            "passed": has_guidance,
            "detail": "guidance seen" if has_guidance else "no guidance yet",
        })

    elif turn_num == 50:
        # No degradation in word count (compare first 10 vs last 10)
        early_wc = [tr.word_count for tr in trs[:10] if tr.word_count > 0]
        recent_wc = [tr.word_count for tr in trs[-10:] if tr.word_count > 0]
        if early_wc and recent_wc:
            early_avg = sum(early_wc) / len(early_wc)
            recent_avg = sum(recent_wc) / len(recent_wc)
            # Allow word count to drop to 30% of early — very lenient
            passed = recent_avg >= early_avg * 0.3
            results.append({
                "description": "[Milestone T50] Word count stability",
                "passed": passed,
                "detail": f"early avg: {early_avg:.0f}, recent avg: {recent_avg:.0f}",
            })

    elif turn_num == 100:
        # Response time not significantly increased vs turn 5
        if len(trs) >= 5:
            early_rt = trs[4].response_time if trs[4].response_time > 0 else 5.0
            current_rt = trs[-1].response_time if trs[-1].response_time > 0 else 5.0
            passed = current_rt <= early_rt * 2.0
            results.append({
                "description": "[Milestone T100] Response time within 2x of turn 5",
                "passed": passed,
                "detail": f"turn 5: {early_rt:.1f}s, turn {turn_num}: {current_rt:.1f}s",
            })

    elif turn_num == 150:
        # Session still alive, no errors
        error_count = sum(1 for tr in trs if tr.error)
        results.append({
            "description": "[Milestone T150] Session alive, minimal errors",
            "passed": error_count <= len(trs) * 0.01,  # < 1% error rate
            "detail": f"{error_count} errors in {len(trs)} turns",
        })

    elif turn_num == 200:
        # Session completes without crash
        error_count = sum(1 for tr in trs if tr.error)
        results.append({
            "description": "[Milestone T200] Session completed without crash",
            "passed": error_count <= len(trs) * 0.01,
            "detail": f"{error_count} errors in {len(trs)} turns — session complete",
        })

    return results


# ---------------------------------------------------------------------------
# Runner class
# ---------------------------------------------------------------------------
class LongConversationRunner:
    def __init__(self, base_url: str = DEFAULT_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.token: str | None = None
        self.results: list[ScenarioResult] = []

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

    async def run_scenario(
        self, client: httpx.AsyncClient, scenario: StressScenario
    ) -> ScenarioResult:
        """Run a single stress scenario (long multi-turn conversation)."""
        print(f"\n{'='*70}")
        print(f"  Scenario #{scenario.id}: {scenario.title}")
        print(f"  Persona: {scenario.persona['name']} | Turns: {scenario.total_turns}")
        print(f"  {scenario.description}")
        print(f"{'='*70}")

        result = ScenarioResult(
            scenario_id=scenario.id,
            title=scenario.title,
            persona_name=scenario.persona["name"],
            total_turns=scenario.total_turns,
            turn_results=[],
        )

        session_id: str | None = None
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        prev_response = ""
        start_time = time.time()

        for turn_num in range(1, scenario.total_turns + 1):
            message = get_message_for_turn(scenario, turn_num)

            # Progress indicator every 10 turns
            if turn_num % 10 == 1 or turn_num == 1:
                elapsed = time.time() - start_time
                print(f"\n  --- Turn {turn_num}/{scenario.total_turns} "
                      f"(elapsed: {elapsed:.0f}s) ---")

            print(f"  [{turn_num}] User: {message[:70]}", end="", flush=True)

            payload = {
                "message": message,
                "language": "en",
                "user_profile": scenario.persona,
            }
            if session_id:
                payload["session_id"] = session_id

            tr = TurnResult(
                turn_number=turn_num,
                user_message=message,
                bot_response="",
                phase="",
                signals={},
                turn_count=0,
                recommended_products=[],
                flow_metadata={},
                validation_results=[],
            )

            try:
                req_start = time.time()
                resp = await client.post(
                    f"{self.base_url}/api/conversation",
                    json=payload,
                    headers=headers,
                    timeout=REQUEST_TIMEOUT,
                )
                tr.response_time = time.time() - req_start

                if resp.status_code != 200:
                    tr.error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                    print(f" -> ERROR: {tr.error}")
                    result.errors += 1
                    # Add failed HTTP validation
                    tr.validation_results.append({
                        "description": "HTTP 200 OK",
                        "passed": False,
                        "detail": tr.error,
                    })
                    result.failed += 1
                    result.turn_results.append(tr)
                    await asyncio.sleep(INTER_TURN_DELAY)
                    continue

                data = resp.json()
                session_id = data.get("session_id")
                tr.bot_response = data.get("response", "")
                tr.phase = data.get("phase", "")
                tr.signals = data.get("signals_collected", {})
                tr.turn_count = data.get("turn_count", 0)
                tr.recommended_products = data.get("recommended_products") or []
                tr.flow_metadata = data.get("flow_metadata") or {}
                tr.word_count = len(tr.bot_response.split())

                # Compact console output
                preview = tr.bot_response[:80].replace("\n", " ")
                print(f" -> ({tr.phase}, {tr.response_time:.1f}s) {preview}...")

                # Per-turn validations
                validations = run_per_turn_validations(
                    tr.bot_response, data, turn_num, tr.response_time, prev_response
                )
                tr.validation_results.extend(validations)

                # Milestone validations
                milestones = run_milestone_validations(result, turn_num)
                tr.validation_results.extend(milestones)

                # Count results
                for vr in tr.validation_results:
                    if vr["passed"]:
                        result.passed += 1
                    else:
                        result.failed += 1
                        # Only print failures (not every check)
                        print(f"      FAIL: {vr['description']} — {vr['detail']}")

                prev_response = tr.bot_response

            except Exception as e:
                tr.error = str(e)
                tr.response_time = time.time() - req_start if 'req_start' in dir() else 0
                print(f" -> EXCEPTION: {e}")
                result.errors += 1
                tr.validation_results.append({
                    "description": "No exception",
                    "passed": False,
                    "detail": str(e),
                })
                result.failed += 1

            result.turn_results.append(tr)

            # Inter-turn delay
            if turn_num < scenario.total_turns:
                await asyncio.sleep(INTER_TURN_DELAY)

        total_elapsed = time.time() - start_time
        total_checks = result.passed + result.failed
        status = "PASS" if result.failed == 0 and result.errors == 0 else "FAIL"
        print(f"\n  Scenario #{scenario.id} Result: {status}")
        print(f"  Checks: {result.passed}/{total_checks} passed | "
              f"Errors: {result.errors} | Time: {total_elapsed:.0f}s")

        return result

    async def run_all(
        self, scenarios: list[StressScenario] | None = None
    ) -> list[ScenarioResult]:
        """Run all (or selected) stress scenarios."""
        target = scenarios or ALL_SCENARIOS
        total_turns = sum(s.total_turns for s in target)

        print(f"\n{'='*70}")
        print(f"  3ioNetra MITRA — Long Conversation Stress Test")
        print(f"  Target: {self.base_url}")
        print(f"  Scenarios: {len(target)} | Total turns: {total_turns}")
        print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Estimated time: ~{total_turns * 3 // 60} min")
        print(f"{'='*70}")

        async with httpx.AsyncClient() as client:
            await self.authenticate(client)

            for scenario in target:
                result = await self.run_scenario(client, scenario)
                self.results.append(result)
                # Brief pause between scenarios
                await asyncio.sleep(3)

        return self.results

    def _compute_aggregate_metrics(self) -> dict:
        """Compute aggregate metrics across all scenarios."""
        metrics = {}

        for sr in self.results:
            sid = sr.scenario_id
            trs = sr.turn_results
            total = len(trs)

            # Error rate
            error_count = sum(1 for tr in trs if tr.error)
            error_rate = error_count / total * 100 if total > 0 else 0

            # Response time trend (by 10-turn windows)
            rt_windows = {}
            for tr in trs:
                window = ((tr.turn_number - 1) // 10) * 10 + 1
                label = f"{window}-{window+9}"
                if label not in rt_windows:
                    rt_windows[label] = []
                if tr.response_time > 0:
                    rt_windows[label].append(tr.response_time)

            rt_trend = {}
            for label, rts in rt_windows.items():
                rt_trend[label] = sum(rts) / len(rts) if rts else 0

            # Repetition rate
            rep_count = 0
            rep_turns = []
            for i in range(1, len(trs)):
                if trs[i].bot_response and trs[i-1].bot_response:
                    sim = SequenceMatcher(
                        None, trs[i].bot_response.lower(), trs[i-1].bot_response.lower()
                    ).ratio()
                    if sim > 0.80:
                        rep_count += 1
                        rep_turns.append(trs[i].turn_number)
            rep_rate = rep_count / max(total - 1, 1) * 100

            # Phase distribution
            phase_dist = {}
            for tr in trs:
                p = tr.phase or "unknown"
                phase_dist[p] = phase_dist.get(p, 0) + 1
            for p in phase_dist:
                phase_dist[p] = round(phase_dist[p] / total * 100, 1)

            # Hollow phrase rate
            hollow_count = 0
            for tr in trs:
                if any(h in tr.bot_response.lower() for h in HOLLOW_PHRASES):
                    hollow_count += 1
            hollow_rate = hollow_count / total * 100 if total > 0 else 0

            # Markdown violation rate
            md_count = 0
            md_patterns = [r"^#{1,6}\s", r"^\s*[-*]\s", r"^\d+\.\s", r"\*\*[^*]+\*\*"]
            for tr in trs:
                for line in tr.bot_response.split("\n"):
                    if any(re.search(pat, line) for pat in md_patterns):
                        md_count += 1
                        break
            md_rate = md_count / total * 100 if total > 0 else 0

            # Word count trend (by 10-turn windows)
            wc_windows = {}
            for tr in trs:
                window = ((tr.turn_number - 1) // 10) * 10 + 1
                label = f"{window}-{window+9}"
                if label not in wc_windows:
                    wc_windows[label] = []
                if tr.word_count > 0:
                    wc_windows[label].append(tr.word_count)

            wc_trend = {}
            for label, wcs in wc_windows.items():
                wc_trend[label] = sum(wcs) / len(wcs) if wcs else 0

            # Guidance oscillation (count of guidance→listening transitions)
            oscillation_count = 0
            guidance_turns = []
            for i in range(1, len(trs)):
                if trs[i-1].phase == "guidance" and trs[i].phase in ("listening", "clarification"):
                    oscillation_count += 1
                if trs[i].phase == "guidance":
                    guidance_turns.append(trs[i].turn_number)

            # Spacing between guidance
            guidance_spacings = []
            for i in range(1, len(guidance_turns)):
                guidance_spacings.append(guidance_turns[i] - guidance_turns[i-1])

            metrics[sid] = {
                "error_rate": round(error_rate, 2),
                "rt_trend": rt_trend,
                "repetition_rate": round(rep_rate, 2),
                "repetition_turns": rep_turns,
                "phase_distribution": phase_dist,
                "hollow_phrase_rate": round(hollow_rate, 2),
                "markdown_violation_rate": round(md_rate, 2),
                "wc_trend": wc_trend,
                "oscillation_count": oscillation_count,
                "guidance_turns": guidance_turns,
                "guidance_spacings": guidance_spacings,
            }

        return metrics

    def _ascii_bar(self, value: float, max_value: float, width: int = 30) -> str:
        """Generate an ASCII bar for charts."""
        if max_value <= 0:
            return ""
        bar_len = int(value / max_value * width)
        return "█" * bar_len + "░" * (width - bar_len)

    def generate_report(self) -> str:
        """Generate JSON + Markdown reports."""
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        metrics = self._compute_aggregate_metrics()

        # ---- JSON output ----
        json_data = []
        for sr in self.results:
            scenario_json = {
                "scenario_id": sr.scenario_id,
                "title": sr.title,
                "persona": sr.persona_name,
                "total_turns": sr.total_turns,
                "passed": sr.passed,
                "failed": sr.failed,
                "errors": sr.errors,
                "metrics": metrics.get(sr.scenario_id, {}),
                "turns": [],
            }
            for tr in sr.turn_results:
                scenario_json["turns"].append({
                    "turn_number": tr.turn_number,
                    "user_message": tr.user_message,
                    "bot_response": tr.bot_response,
                    "phase": tr.phase,
                    "signals": tr.signals,
                    "turn_count": tr.turn_count,
                    "response_time": round(tr.response_time, 2),
                    "word_count": tr.word_count,
                    "validation_results": tr.validation_results,
                    "error": tr.error,
                })
            json_data.append(scenario_json)

        json_path = RESULTS_DIR / "results.json"
        json_path.write_text(json.dumps(json_data, indent=2, ensure_ascii=False), encoding="utf-8")

        # ---- Markdown report ----
        total_turns_sent = sum(sr.total_turns for sr in self.results)
        total_passed = sum(sr.passed for sr in self.results)
        total_failed = sum(sr.failed for sr in self.results)
        total_errors = sum(sr.errors for sr in self.results)
        total_checks = total_passed + total_failed

        # Aggregate rates
        all_error_rates = [metrics[sid]["error_rate"] for sid in metrics]
        all_rep_rates = [metrics[sid]["repetition_rate"] for sid in metrics]
        all_hollow_rates = [metrics[sid]["hollow_phrase_rate"] for sid in metrics]
        all_md_rates = [metrics[sid]["markdown_violation_rate"] for sid in metrics]

        avg_error_rate = sum(all_error_rates) / len(all_error_rates) if all_error_rates else 0
        avg_rep_rate = sum(all_rep_rates) / len(all_rep_rates) if all_rep_rates else 0
        avg_hollow_rate = sum(all_hollow_rates) / len(all_hollow_rates) if all_hollow_rates else 0
        avg_md_rate = sum(all_md_rates) / len(all_md_rates) if all_md_rates else 0

        # Determine pass/fail per criteria
        criteria_pass = {
            "error_rate": avg_error_rate < 1.0,
            "no_crashes": all(sr.errors < sr.total_turns * 0.01 for sr in self.results),
            "response_time": True,  # Checked per-scenario below
            "repetition_rate": avg_rep_rate < 10.0,
            "hollow_phrase_rate": avg_hollow_rate < 5.0,
            "markdown_rate": avg_md_rate < 5.0,
        }

        # Check response time at turn 200 vs turn 5 for S4
        for sr in self.results:
            if sr.total_turns >= 200 and len(sr.turn_results) >= 200:
                t5 = sr.turn_results[4].response_time if sr.turn_results[4].response_time > 0 else 5
                t200 = sr.turn_results[-1].response_time if sr.turn_results[-1].response_time > 0 else 5
                if t200 > t5 * 2:
                    criteria_pass["response_time"] = False

        all_criteria_pass = all(criteria_pass.values())

        lines = [
            "# 3ioNetra Mitra — Long Conversation Stress Test Report",
            "",
            f"**Run:** {now}",
            f"**Target:** `{self.base_url}`",
            f"**Scenarios:** {len(self.results)}",
            f"**Total Turns Sent:** {total_turns_sent}",
            f"**Total Checks:** {total_checks} | **Passed:** {total_passed} | "
            f"**Failed:** {total_failed} | **Errors:** {total_errors}",
            f"**Check Pass Rate:** {total_passed / total_checks * 100:.1f}%" if total_checks > 0 else "**Pass Rate:** N/A",
            "",
            "## Success Criteria",
            "",
            f"| Criterion | Threshold | Actual | Status |",
            f"|-----------|-----------|--------|--------|",
            f"| Error rate | < 1% | {avg_error_rate:.2f}% | {'PASS' if criteria_pass['error_rate'] else 'FAIL'} |",
            f"| No session crashes | < 1% errors | {'all ok' if criteria_pass['no_crashes'] else 'FAIL'} | {'PASS' if criteria_pass['no_crashes'] else 'FAIL'} |",
            f"| Response time T200 < 2x T5 | 2x | {'ok' if criteria_pass['response_time'] else 'FAIL'} | {'PASS' if criteria_pass['response_time'] else 'FAIL'} |",
            f"| Repetition rate | < 10% | {avg_rep_rate:.2f}% | {'PASS' if criteria_pass['repetition_rate'] else 'FAIL'} |",
            f"| Hollow phrase rate | < 5% | {avg_hollow_rate:.2f}% | {'PASS' if criteria_pass['hollow_phrase_rate'] else 'FAIL'} |",
            f"| Markdown violation rate | < 5% | {avg_md_rate:.2f}% | {'PASS' if criteria_pass['markdown_rate'] else 'FAIL'} |",
            "",
            f"**Overall: {'PASS' if all_criteria_pass else 'FAIL'}**",
            "",
            "---",
            "",
        ]

        # ---- Per-scenario summary table ----
        lines.append("## Per-Scenario Summary\n")
        lines.append("| # | Scenario | Turns | Errors | Avg RT | Rep% | Hollow% | MD% | Phase Distribution |")
        lines.append("|---|----------|-------|--------|--------|------|---------|-----|-------------------|")

        for sr in self.results:
            m = metrics[sr.scenario_id]
            all_rts = [tr.response_time for tr in sr.turn_results if tr.response_time > 0]
            avg_rt = sum(all_rts) / len(all_rts) if all_rts else 0

            phase_str = ", ".join(f"{p}: {pct}%" for p, pct in sorted(m["phase_distribution"].items()))

            lines.append(
                f"| S{sr.scenario_id} | {sr.title} | {sr.total_turns} | "
                f"{m['error_rate']:.1f}% | {avg_rt:.1f}s | "
                f"{m['repetition_rate']:.1f}% | {m['hollow_phrase_rate']:.1f}% | "
                f"{m['markdown_violation_rate']:.1f}% | {phase_str} |"
            )

        lines.append("")
        lines.append("---")
        lines.append("")

        # ---- Response time trend per scenario ----
        lines.append("## Response Time Trend (avg per 10-turn window)\n")
        for sr in self.results:
            m = metrics[sr.scenario_id]
            lines.append(f"### S{sr.scenario_id}: {sr.title}\n")
            lines.append("```")
            max_rt = max(m["rt_trend"].values()) if m["rt_trend"] else 1
            for label, avg_rt in m["rt_trend"].items():
                bar = self._ascii_bar(avg_rt, max(max_rt, 1), 30)
                lines.append(f"  T{label:>8s} | {bar} {avg_rt:.1f}s")
            lines.append("```")
            lines.append("")

        lines.append("---")
        lines.append("")

        # ---- Word count trend per scenario ----
        lines.append("## Word Count Trend (avg per 10-turn window)\n")
        for sr in self.results:
            m = metrics[sr.scenario_id]
            lines.append(f"### S{sr.scenario_id}: {sr.title}\n")
            lines.append("```")
            max_wc = max(m["wc_trend"].values()) if m["wc_trend"] else 1
            for label, avg_wc in m["wc_trend"].items():
                bar = self._ascii_bar(avg_wc, max(max_wc, 1), 30)
                lines.append(f"  T{label:>8s} | {bar} {avg_wc:.0f}w")
            lines.append("```")
            lines.append("")

        lines.append("---")
        lines.append("")

        # ---- Repetition incidents ----
        lines.append("## Repetition Incidents\n")
        any_reps = False
        for sr in self.results:
            m = metrics[sr.scenario_id]
            if m["repetition_turns"]:
                any_reps = True
                lines.append(f"- **S{sr.scenario_id} ({sr.title}):** turns {m['repetition_turns']}")
        if not any_reps:
            lines.append("No repetition incidents detected (>80% similarity threshold).")
        lines.append("")
        lines.append("---")
        lines.append("")

        # ---- Guidance oscillation ----
        lines.append("## Guidance Oscillation Analysis\n")
        for sr in self.results:
            m = metrics[sr.scenario_id]
            lines.append(f"### S{sr.scenario_id}: {sr.title}")
            lines.append(f"- Guidance→Listening transitions: {m['oscillation_count']}")
            lines.append(f"- Guidance turns: {m['guidance_turns'][:20]}{'...' if len(m['guidance_turns']) > 20 else ''}")
            if m["guidance_spacings"]:
                avg_spacing = sum(m["guidance_spacings"]) / len(m["guidance_spacings"])
                min_spacing = min(m["guidance_spacings"])
                lines.append(f"- Avg spacing between guidance: {avg_spacing:.1f} turns (min: {min_spacing})")
            lines.append("")

        lines.append("---")
        lines.append("")

        # ---- All validation failures ----
        lines.append("## Validation Failures (all)\n")
        failure_count = 0
        for sr in self.results:
            scenario_failures = []
            for tr in sr.turn_results:
                for vr in tr.validation_results:
                    if not vr["passed"]:
                        scenario_failures.append((tr.turn_number, vr["description"], vr["detail"]))

            if scenario_failures:
                lines.append(f"### S{sr.scenario_id}: {sr.title} ({len(scenario_failures)} failures)\n")
                for turn_num, desc, detail in scenario_failures[:50]:  # Limit to 50 per scenario
                    lines.append(f"- Turn {turn_num}: {desc} — {detail}")
                    failure_count += 1
                if len(scenario_failures) > 50:
                    lines.append(f"- ... and {len(scenario_failures) - 50} more")
                lines.append("")

        if failure_count == 0:
            lines.append("No validation failures!")
        lines.append("")
        lines.append("---")
        lines.append("")

        # ---- Improvement Plan (if criteria not met) ----
        if not all_criteria_pass:
            lines.append("## Improvement Plan\n")
            lines.append("The following issues were detected and need attention:\n")

            if not criteria_pass["error_rate"]:
                lines.append("### 1. High Error Rate")
                lines.append("- **Issue:** Error rate exceeds 1% threshold")
                lines.append("- **Root cause:** Likely session storage issues (unbounded conversation_history)")
                lines.append("- **Fix:** Implement history pruning in `SessionState.add_message()` — "
                           "keep last N messages (e.g., 50) and archive older ones")
                lines.append("- **File:** `backend/models/session.py:add_message()`")
                lines.append("")

            if not criteria_pass["response_time"]:
                lines.append("### 2. Response Time Degradation")
                lines.append("- **Issue:** Response time at turn 200 exceeds 2x turn 5")
                lines.append("- **Root cause:** Unbounded `conversation_history` causes increasing "
                           "serialization/deserialization overhead in Redis/MongoDB")
                lines.append("- **Fix:** (a) Prune conversation_history to last 50 messages. "
                           "(b) Cap `memory.user_quotes` and `memory.emotional_arc` to last 20 entries. "
                           "(c) Add session size monitoring.")
                lines.append("- **Files:** `backend/models/session.py`, `backend/models/memory_context.py`")
                lines.append("")

            if not criteria_pass["repetition_rate"]:
                lines.append("### 3. High Repetition Rate")
                lines.append("- **Issue:** Bot repeats itself in >10% of consecutive turns")
                lines.append("- **Root cause:** 8-message LLM window (`llm/service.py:614`) causes "
                           "context loss. Bot doesn't remember what it said earlier.")
                lines.append("- **Fix:** (a) Increase LLM history window from 8 to 16-20 messages. "
                           "(b) Add response deduplication — track last 5 response hashes and reject "
                           "near-duplicates. (c) Include a 'recent themes summary' in the prompt.")
                lines.append("- **Files:** `backend/llm/service.py:610-627`, "
                           "`backend/services/response_composer.py`")
                lines.append("")

            if not criteria_pass["hollow_phrase_rate"]:
                lines.append("### 4. Hollow Phrase Usage")
                lines.append("- **Issue:** Hollow phrases appear in >5% of turns")
                lines.append("- **Fix:** (a) Add hollow phrase list to system instruction negative examples. "
                           "(b) Add post-processing filter that rewrites hollow phrases. "
                           "(c) Strengthen the 'no hollow phrases' instruction in YAML prompt.")
                lines.append("- **File:** `backend/prompts/spiritual_mitra.yaml`")
                lines.append("")

            if not criteria_pass["markdown_rate"]:
                lines.append("### 5. Markdown Formatting Violations")
                lines.append("- **Issue:** Markdown appears in >5% of responses")
                lines.append("- **Fix:** (a) Add markdown stripping in post-processing "
                           "(`_postprocess_and_save`). (b) Strengthen 'no markdown' instruction in prompt.")
                lines.append("- **Files:** `backend/routers/chat.py:_postprocess_and_save()`, "
                           "`backend/prompts/spiritual_mitra.yaml`")
                lines.append("")

            if not criteria_pass["no_crashes"]:
                lines.append("### 6. Session Crashes")
                lines.append("- **Issue:** Session crashes detected (>1% error rate in a scenario)")
                lines.append("- **Root cause:** Likely OOM or serialization failures from unbounded session data")
                lines.append("- **Fix:** (a) Add session size monitoring and alerts. "
                           "(b) Implement graceful degradation — if session save fails, continue with "
                           "in-memory state. (c) Add circuit breaker around session persistence.")
                lines.append("- **Files:** `backend/services/session_manager.py`, "
                           "`backend/services/companion_engine.py`")
                lines.append("")

            # Always mention the known oscillation bug
            lines.append("### Known: Oscillation Control Bug")
            lines.append("- **Issue:** `last_guidance_turn` is never set after guidance "
                       "(companion_engine.py:790)")
            lines.append("- **Impact:** Bot may flip-flop between guidance and listening every turn")
            lines.append("- **Fix:** Set `session.last_guidance_turn = session.turn_count` after "
                       "guidance response is generated")
            lines.append("- **File:** `backend/services/companion_engine.py:790`")
            lines.append("")

        else:
            lines.append("## Improvement Plan\n")
            lines.append("All success criteria met! No immediate action required.\n")
            lines.append("**Known issues to monitor:**")
            lines.append("- `last_guidance_turn` is never set → oscillation control is non-functional")
            lines.append("- `conversation_history` grows unboundedly — will become a problem at higher turn counts")
            lines.append("- 8-message LLM window limits long-term context recall")
            lines.append("")

        # Footer
        lines.append("---")
        lines.append("")
        lines.append(f"*Generated by `test_long_conversation.py` on {now}*")

        report = "\n".join(lines)
        report_path = RESULTS_DIR / "stress_test_report.md"
        report_path.write_text(report, encoding="utf-8")

        print(f"\n{'='*70}")
        print(f"  Reports saved:")
        print(f"    JSON:     {json_path}")
        print(f"    Markdown: {report_path}")
        print(f"  Overall: {'PASS' if all_criteria_pass else 'FAIL'}")
        print(f"  Checks: {total_checks} | Passed: {total_passed} | Failed: {total_failed}")
        print(f"{'='*70}")

        return str(report_path)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="3ioNetra Mitra — Long Conversation Stress Test (50-200 turns)"
    )
    parser.add_argument("--url", default=DEFAULT_BASE_URL, help="API base URL")
    parser.add_argument("--scenario", type=int, help="Run a single scenario by ID (1-6)")
    args = parser.parse_args()

    runner = LongConversationRunner(base_url=args.url)

    # Filter scenarios
    scenarios = ALL_SCENARIOS
    if args.scenario:
        scenarios = [s for s in ALL_SCENARIOS if s.id == args.scenario]
        if not scenarios:
            print(f"Scenario #{args.scenario} not found. Valid IDs: 1-6")
            sys.exit(1)

    # Run
    asyncio.run(runner.run_all(scenarios))

    # Generate report
    runner.generate_report()


if __name__ == "__main__":
    main()
