"""
Test Script for Spiritual Companion Bot Use Cases
Systematically tests all 20 use cases and records observations
"""

import asyncio
import httpx
import json
from datetime import datetime
from pathlib import Path

# Configuration
BASE_URL = "http://localhost:8080"
RESULTS_FILE = Path(__file__).parent.parent.parent.parent / "docs" / "use_case_test_results.json"

# Define test scenarios for each use case
USE_CASE_TESTS = {
    "case_1_sadness_loss": {
        "name": "Deep Sadness & Loss",
        "messages": [
            "Hi",
            "I lost my mother last month and I can't stop crying",
            "She was everything to me. I feel so alone now.",
            "Nothing seems to matter anymore without her.",
        ],
        "expected_behaviors": [
            "Warm greeting without jumping to wisdom",
            "Empathetic acknowledgment of loss",
            "Gentle listening and validation",
            "After context, offer relevant wisdom about death/grief (Gita teachings on soul)"
        ]
    },
    
    "case_2_anger_family": {
        "name": "Anger & Family Conflict",
        "messages": [
            "Hey",
            "I am so angry at my brother right now",
            "He stole money from our family business and lied about it",
            "I want to never speak to him again. But my parents keep pushing me to forgive.",
        ],
        "expected_behaviors": [
            "Friendly greeting",
            "Allow venting without judgment",
            "Understand the depth of betrayal",
            "Gently introduce teachings on anger/forgiveness when appropriate"
        ]
    },
    
    "case_3_anxiety_future": {
        "name": "Anxiety & Fear of Future",
        "messages": [
            "Namaste",
            "I'm constantly worried about my future",
            "What if I fail in my career? What if I can't provide for my family?",
            "These thoughts keep me up at night",
        ],
        "expected_behaviors": [
            "Warm acknowledgment",
            "Validate anxiety without amplifying",
            "Explore the root of fears",
            "Share Gita teachings on surrendering outcomes"
        ]
    },
    
    "case_4_loneliness": {
        "name": "Loneliness & Isolation",
        "messages": [
            "Hello",
            "I feel very lonely these days",
            "I moved to a new city for work and have no friends here",
            "Sometimes I wonder if anyone even cares about me",
        ],
        "expected_behaviors": [
            "Warm presence",
            "Acknowledge the pain of isolation",
            "Suggest spiritual community connections",
            "Share wisdom on divine companionship"
        ]
    },
    
    "case_5_self_doubt": {
        "name": "Self-Doubt & Low Self-Worth",
        "messages": [
            "Hi",
            "I feel like such a failure",
            "Everyone around me seems to be succeeding and I'm stuck",
            "Maybe I'm just not good enough for anything",
        ],
        "expected_behaviors": [
            "Warm greeting",
            "Unconditional positive regard",
            "Challenge self-criticism gently",
            "Introduce Vedantic teaching on true Self"
        ]
    },
    
    "case_6_life_transition": {
        "name": "Major Life Changes",
        "messages": [
            "Pranam",
            "I just retired after 35 years of work",
            "I don't know what to do with myself now",
            "My whole identity was my job. Who am I now?",
        ],
        "expected_behaviors": [
            "Respectful greeting",
            "Honor the magnitude of transition",
            "Introduce ashrama concept",
            "Guide toward new spiritual opportunities"
        ]
    },
    
    "case_7_illness": {
        "name": "Illness & Physical Suffering",
        "messages": [
            "Hello",
            "I was just diagnosed with a chronic illness",
            "The doctors say I'll have to live with this pain forever",
            "I don't understand why this is happening to me",
        ],
        "expected_behaviors": [
            "Deep compassion for suffering",
            "Avoid dismissing physical pain",
            "Share teachings on body-soul distinction",
            "Suggest healing prayers/mantras"
        ]
    },
    
    "case_8_career_stress": {
        "name": "Career Crisis & Professional Stress",
        "messages": [
            "Hey",
            "I hate my job so much",
            "My boss is toxic and the work feels meaningless",
            "But I can't quit because I have bills to pay",
        ],
        "expected_behaviors": [
            "Allow venting about work",
            "Acknowledge the practical constraints",
            "Introduce karma yoga principles",
            "Help reframe work as spiritual practice"
        ]
    },
    
    "case_9_deeper_practice": {
        "name": "Seeking Deeper Practice",
        "messages": [
            "Namaste",
            "I want to deepen my spiritual practice",
            "I've been doing basic meditation but feel stuck",
            "How can I grow spiritually?",
        ],
        "expected_behaviors": [
            "Warm encouragement",
            "Assess current practice level",
            "Suggest appropriate paths (bhakti, jnana, etc.)",
            "Provide specific practice recommendations"
        ]
    },
    
    "case_10_deity_devotion": {
        "name": "Deity & Devotion Questions",
        "messages": [
            "Hi",
            "I want to connect more with Lord Shiva",
            "But I don't know how to start",
            "What practices would help me feel closer to Mahadev?",
        ],
        "expected_behaviors": [
            "Warm response",
            "Share about Shiva's qualities",
            "Suggest specific practices (mantras, puja)",
            "Recommend relevant temples"
        ]
    },
    
    "case_11_philosophical_doubts": {
        "name": "Doubts & Philosophical Questions",
        "messages": [
            "Hello",
            "I have doubts about whether God exists",
            "How can there be a loving God when there's so much suffering?",
            "Sometimes I question everything I was taught",
        ],
        "expected_behaviors": [
            "Welcome questions without judgment",
            "Engage thoughtfully with theodicy",
            "Draw from philosophical texts",
            "Honor the journey of inquiry"
        ]
    },
    
    "case_12_guilt_atonement": {
        "name": "Guilt & Need for Atonement",
        "messages": [
            "Pranam",
            "I did something terrible years ago",
            "I hurt someone deeply and I can never undo it",
            "The guilt is eating me alive. Can I ever be forgiven?",
        ],
        "expected_behaviors": [
            "Non-judgmental listening",
            "Explain karma as learning",
            "Suggest purification practices",
            "Guide toward self-forgiveness"
        ]
    },
    
    "case_13_marriage_challenges": {
        "name": "Marriage & Relationship Challenges",
        "messages": [
            "Hey",
            "My marriage is falling apart",
            "We used to be so happy but now we just fight constantly",
            "I don't know if we can save this",
        ],
        "expected_behaviors": [
            "Empathetic listening",
            "Honor relationship complexity",
            "Share teachings on partnership",
            "Suggest spiritual reconciliation practices"
        ]
    },
    
    "case_14_parenting": {
        "name": "Parenting Concerns",
        "messages": [
            "Namaste",
            "I'm struggling with my teenage son",
            "He's become so rebellious and disrespectful",
            "I feel like I'm losing my child",
        ],
        "expected_behaviors": [
            "Validate parenting challenges",
            "Share wisdom on nurturing",
            "Suggest family spiritual practices",
            "Discuss parental dharma"
        ]
    },
    
    "case_15_social_injustice": {
        "name": "Social Injustice Concerns",
        "messages": [
            "Hi",
            "I'm deeply troubled by injustice in our society",
            "There's so much inequality and corruption",
            "How do I stay spiritually centered when the world seems so broken?",
        ],
        "expected_behaviors": [
            "Acknowledge valid concerns",
            "Introduce karma yoga for action",
            "Balance detachment with engagement",
            "Guide toward constructive service"
        ]
    },
    
    "case_16_dark_night": {
        "name": "Dark Night of the Soul",
        "messages": [
            "Hello",
            "I used to feel God's presence so strongly",
            "But now I feel nothing. Like God has abandoned me.",
            "I pray but there's only silence",
        ],
        "expected_behaviors": [
            "Deep compassion",
            "Normalize as spiritual phase",
            "Share saints' experiences",
            "Encourage continued practice"
        ]
    },
    
    "case_17_addiction": {
        "name": "Addiction & Compulsive Behaviors",
        "messages": [
            "Hey",
            "I can't stop drinking",
            "I've tried so many times but I always fail",
            "I feel so ashamed and weak",
        ],
        "expected_behaviors": [
            "Non-judgmental support",
            "Teach about attachment/craving",
            "Suggest surrender practices",
            "Recommend professional help alongside"
        ]
    },
    
    "case_18_existential_crisis": {
        "name": "Existential Crisis",
        "messages": [
            "Hi",
            "What's the point of anything?",
            "I have everything - job, family, money - but I feel empty inside",
            "Is this all there is to life?",
        ],
        "expected_behaviors": [
            "Take questions seriously",
            "Engage with meaning-making",
            "Introduce moksha as life's goal",
            "Explore svadharma discovery"
        ]
    },
    
    "case_19_festival_guidance": {
        "name": "Festival & Ritual Guidance",
        "messages": [
            "Namaste",
            "Navratri is coming and I want to observe it properly",
            "I live abroad and don't have a temple nearby",
            "Can you guide me on how to celebrate?",
        ],
        "expected_behaviors": [
            "Practical guidance",
            "Explain festival significance",
            "Adapt for diaspora context",
            "Provide specific rituals"
        ]
    },
    
    "case_20_meditation_issues": {
        "name": "Meditation Troubleshooting",
        "messages": [
            "Hello",
            "I'm having trouble with meditation",
            "My mind won't stop racing no matter how hard I try",
            "Am I doing something wrong?",
        ],
        "expected_behaviors": [
            "Normalize difficulties",
            "Diagnose specific issues",
            "Suggest techniques",
            "Encourage persistence"
        ]
    }
}


# ------------------------------------------------------------------
# MOCK USER PROFILES (Based on seed_users.py archetypes)
# ------------------------------------------------------------------
TEST_PROFILES = {
    "arjun": {
        "name": "Arjun",
        "age_group": "30-40",
        "gender": "male",
        "profession": "Software Engineer",
        "preferred_deity": "Shiva",
        "location": "Bangalore, India",
        "spiritual_interests": ["meditation", "yoga", "vedanta"]
    },
    "meera": {
        "name": "Meera",
        "age_group": "50-60",
        "gender": "female",
        "profession": "Teacher",
        "preferred_deity": "Krishna",
        "location": "Delhi, India",
        "spiritual_interests": ["bhakti", "kirtan", "temples"]
    },
    "rohan": {
        "name": "Rohan",
        "age_group": "18-25",
        "gender": "male",
        "profession": "University Student",
        "preferred_deity": "Hanuman",
        "location": "Mumbai, India",
        "spiritual_interests": ["strength", "discipline", "service"]
    },
    "vikram": {
        "name": "Vikram",
        "age_group": "60+",
        "gender": "male",
        "profession": "Retired Banker",
        "preferred_deity": "Ram",
        "location": "Pune, India",
        "spiritual_interests": ["dharma", "philosophy", "charity"]
    }
}

# Map use cases to most relevant profile
CASE_PROFILE_MAP = {
    "case_1_sadness_loss": "meera",
    "case_2_anger_family": "arjun",
    "case_3_anxiety_future": "arjun", # Career anxiety fits young professional
    "case_4_loneliness": "rohan", # Student in new city
    "case_5_self_doubt": "rohan",
    "case_6_life_transition": "vikram", # Retirement case
    "case_7_illness": "vikram",
    "case_8_career_stress": "arjun",
    "case_9_deeper_practice": "meera",
    "case_10_deity_devotion": "arjun", # Asking about Shiva (Arjun's deity)
    "case_11_philosophical_doubts": "rohan",
    "case_12_guilt_atonement": "vikram",
    "case_13_marriage_challenges": "arjun",
    "case_14_parenting": "meera",
    "case_15_social_injustice": "rohan",
    "case_16_dark_night": "meera",
    "case_17_addiction": "rohan",
    "case_18_existential_crisis": "arjun",
    "case_19_festival_guidance": "meera",
    "case_20_meditation_issues": "arjun"
}


async def test_use_case(client: httpx.AsyncClient, case_id: str, case_data: dict) -> dict:
    """Test a single use case and record results"""
    print(f"\n{'='*60}")
    print(f"Testing: {case_data['name']}")
    
    # Select Profile
    profile_key = CASE_PROFILE_MAP.get(case_id, "arjun")
    profile = TEST_PROFILES[profile_key]
    print(f"Profile: {profile['name']} ({profile['age_group']}, {profile['profession']}, {profile['preferred_deity']})")
    print(f"{'='*60}")
    
    session_id = None
    results = {
        "case_id": case_id,
        "name": case_data["name"],
        "profile": profile,
        "messages": [],
        "responses": [],
        "observations": [],
        "issues": [],
        "passed_expectations": [],
        "failed_expectations": [],
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        for i, message in enumerate(case_data["messages"]):
            print(f"\n> {profile['name']}: {message}")
            
            payload = {
                "message": message,
                "language": "en",
                "user_profile": profile  # INJECT PROFILE HERE
            }
            
            if session_id:
                payload["session_id"] = session_id
            
            response = await client.post(
                f"{BASE_URL}/api/conversation",
                json=payload,
                timeout=60.0
            )
            
            if response.status_code != 200:
                print(f"  ERROR: {response.status_code} - {response.text}")
                results["issues"].append(f"API error on message {i+1}: {response.status_code}")
                continue
            
            data = response.json()
            session_id = data.get("session_id")
            bot_response = data.get("response", "")
            phase = data.get("phase", "unknown")
            
            print(f"< Bot ({phase}): {bot_response[:200]}...")
            
            results["messages"].append(message)
            results["responses"].append({
                "text": bot_response,
                "phase": phase,
                "turn": i + 1
            })
            
            # Allow some time between messages
            await asyncio.sleep(1)
    
    except Exception as e:
        results["issues"].append(f"Exception: {str(e)}")
        print(f"  ERROR: {e}")
    
    return results


async def run_all_tests():
    """Run all use case tests"""
    print("\n" + "="*70)
    print(" SPIRITUAL COMPANION BOT - USE CASE TESTING ")
    print("="*70)
    print(f" Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    all_results = []
    
    async with httpx.AsyncClient() as client:
        # Test each use case
        for case_id, case_data in USE_CASE_TESTS.items():
            result = await test_use_case(client, case_id, case_data)
            all_results.append(result)
            
            # Brief pause between test cases
            await asyncio.sleep(2)
    
    # Save results
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_FILE, 'w') as f:
        json.dump({
            "test_run": datetime.now().isoformat(),
            "total_cases": len(all_results),
            "results": all_results
        }, f, indent=2)
    
    print("\n" + "="*70)
    print(f" TEST COMPLETE - Results saved to: {RESULTS_FILE}")
    print("="*70)
    
    return all_results


async def test_single_case(case_id: str):
    """Test a single use case by ID"""
    if case_id not in USE_CASE_TESTS:
        print(f"Unknown case: {case_id}")
        print(f"Available: {list(USE_CASE_TESTS.keys())}")
        return
    
    async with httpx.AsyncClient() as client:
        result = await test_use_case(client, case_id, USE_CASE_TESTS[case_id])
        
    print("\n" + "="*60)
    print("RESULT SUMMARY:")
    print("="*60)
    for i, resp in enumerate(result["responses"]):
        print(f"\nTurn {i+1} ({resp['phase']}):")
        print(f"  {resp['text'][:150]}...")
    
    return result


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Test specific case
        asyncio.run(test_single_case(sys.argv[1]))
    else:
        # Run all tests
        asyncio.run(run_all_tests())
