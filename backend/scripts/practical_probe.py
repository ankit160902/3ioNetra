import asyncio
import os
import sys
from typing import List, Dict, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.intent_agent import get_intent_agent

practical_scenarios = [
    # 🥗 Diet & Nutrition (Sattvic Living)
    # Note: Both ASKING_INFO and SEEKING_GUIDANCE are valid for direct planning questions.
    # recommend_products = True only for explicit product/item mentions.
    {"id": 1,  "name": "Sattvic Start",       "message": "I want to switch to a Sattvic diet. Can you give me a full-day diet routine that keeps me light yet energetic?", "needs_direct": True, "allowed_intents": ["ASKING_INFO","SEEKING_GUIDANCE"], "should_recommend": False},
    {"id": 2,  "name": "Weight Management",   "message": "I'm trying to lose some weight while staying spiritually aligned. Suggest a Dharmic meal plan for the day.", "needs_direct": True, "allowed_intents": ["ASKING_INFO","SEEKING_GUIDANCE"], "should_recommend": False},
    {"id": 3,  "name": "Busy Sattvic Lunch",  "message": "I have no time for long breaks. What's a quick, healthy, and Sattvic lunch I can have at my desk?", "needs_direct": True, "allowed_intents": ["ASKING_INFO","SEEKING_GUIDANCE"], "should_recommend": False},
    {"id": 4,  "name": "Ekadashi Fasting",    "message": "I want to start Ekadashi fasting. How should I plan my meals for the day before and after?", "needs_direct": True, "allowed_intents": ["ASKING_INFO","SEEKING_GUIDANCE"], "should_recommend": False},
    {"id": 5,  "name": "Ayurvedic Detox",     "message": "I feel heavy and toxic. Give me a one-day Ayurvedic detox diet plan.", "needs_direct": True, "allowed_intents": ["ASKING_INFO","SEEKING_GUIDANCE"], "should_recommend": True},

    # 📿 Puja & Ritual Planning
    {"id": 6,  "name": "Daily Ganesha Puja",  "message": "I want to establish a solid morning puja routine. Plan me a step-by-step 15-minute daily puja for Lord Ganesha.", "needs_direct": True, "allowed_intents": ["ASKING_INFO","SEEKING_GUIDANCE"], "should_recommend": True},
    {"id": 7,  "name": "Business Start Puja", "message": "I'm starting a new business. Which puja should I do, and can you list exactly how I can perform it at home?", "needs_direct": True, "allowed_intents": ["ASKING_INFO","SEEKING_GUIDANCE"], "should_recommend": True},
    {"id": 8,  "name": "Shiva Abhishekam",    "message": "I want to perform a simple Shiva Abhishekam at home today. What items do I need and what are the steps?", "needs_direct": True, "allowed_intents": ["ASKING_INFO","SEEKING_GUIDANCE","PRODUCT_SEARCH"], "should_recommend": True},
    {"id": 9,  "name": "Family Aarti",        "message": "Help me plan a peaceful evening aarti routine for my family. What mantras should we chant?", "needs_direct": True, "allowed_intents": ["ASKING_INFO","SEEKING_GUIDANCE"], "should_recommend": True},
    {"id": 10, "name": "Altar Reset",         "message": "I've moved my altar. How do I 're-energize' the space dharmically? List the steps.", "needs_direct": True, "allowed_intents": ["ASKING_INFO","SEEKING_GUIDANCE"], "should_recommend": None},  # Accept both True/False

    # 🧘 Yoga & Mindfulness
    {"id": 11, "name": "Energy Booster Yoga", "message": "I feel lethargic in the mornings. Give me a 20-minute yoga routine to stay active all day.", "needs_direct": True, "allowed_intents": ["ASKING_INFO","SEEKING_GUIDANCE"], "should_recommend": False},
    {"id": 12, "name": "Student Focus Yoga",  "message": "I'm a student and my concentration is poor. Plan me a yoga and pranayama routine to improve focus.", "needs_direct": True, "allowed_intents": ["ASKING_INFO","SEEKING_GUIDANCE"], "should_recommend": False},
    {"id": 13, "name": "Bedtime Relax Yoga",  "message": "I can't sleep because of work stress. Give me a bedtime yoga routine to relax my mind and body.", "needs_direct": True, "allowed_intents": ["ASKING_INFO","SEEKING_GUIDANCE"], "should_recommend": None},  # Accept both True/False
    {"id": 14, "name": "Desk Yoga Routine",   "message": "I sit for 8 hours a day. Give me a routine of simple stretches I can do at my chair every two hours.", "needs_direct": True, "allowed_intents": ["ASKING_INFO","SEEKING_GUIDANCE"], "should_recommend": False},
    {"id": 15, "name": "Holistic Sunday",     "message": "I want to dedicate my Sunday to self-care. Plan a full day involving Yoga, Diet, and Meditation.", "needs_direct": True, "allowed_intents": ["ASKING_INFO","SEEKING_GUIDANCE"], "should_recommend": False},
]

async def run_practical_probe():
    intent_agent = get_intent_agent()
    
    print(f"\n{'='*105}")
    print(f"  3ioNetra Practical Planning: Intent Validation (15 Scenarios)")
    print(f"{'='*105}")
    print(f"{'ID':<4} | {'SCENARIO':<25} | {'DIRECT?':<8} | {'INTENT':<18} | {'PROD?':<6} | {'STATUS'}")
    print(f"{'='*105}")
    
    passed = 0
    total = len(practical_scenarios)
    
    for s in sorted(practical_scenarios, key=lambda x: x['id']):
        try:
            await asyncio.sleep(1.5)
            analysis = await intent_agent.analyze_intent(s['message'])
            
            got_direct   = analysis.get('needs_direct_answer')
            got_intent   = analysis.get('intent', '')
            got_rec      = analysis.get('recommend_products')

            direct_ok  = (got_direct == s['needs_direct'])
            intent_ok  = (got_intent in s['allowed_intents'])
            # None means: accept whatever the LLM decides — it's a judgment call
            rec_ok = True if s['should_recommend'] is None else (got_rec == s['should_recommend'])
            
            all_ok  = direct_ok and intent_ok and rec_ok
            status  = "✅ PASS" if all_ok else "❌ FAIL"
            if all_ok: passed += 1
            
            print(f"{s['id']:<4} | {s['name']:<25} | {str(got_direct):<8} | {got_intent:<18} | {str(got_rec):<6} | {status}")
            
            if not all_ok:
                if not direct_ok: print(f"     -> Direct: got {got_direct}, expected {s['needs_direct']}")
                if not intent_ok: print(f"     -> Intent: got {got_intent}, expected one of {s['allowed_intents']}")
                if not rec_ok:    print(f"     -> Rec:    got {got_rec}, expected {s['should_recommend']}")
                
        except Exception as e:
            print(f"{s['id']:<4} | {s['name']:<25} | ERROR: {str(e)[:60]}")
            if "429" in str(e):
                print("     -> Rate limit — sleeping 6s…")
                await asyncio.sleep(6)

    pct = int(100 * passed / total)
    print(f"{'='*105}")
    print(f"  FINAL: {passed}/{total} ({pct}%) Practical Scenarios Passed")
    print(f"{'='*105}\n")

if __name__ == "__main__":
    asyncio.run(run_practical_probe())
